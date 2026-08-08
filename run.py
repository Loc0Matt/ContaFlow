"""Punto de entrada de ContaFlow para escritorio.

Levanta el servidor local, abre el navegador y muestra una ventana de control.
Es el archivo que PyInstaller convierte en ContaFlow.exe.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser

import uvicorn

from contaflow.config import APP_NAME, APP_VERSION, DIR_DATOS, HOST, PUERTO

#: Archivo donde queda el registro cuando la aplicación corre sin consola.
RUTA_REGISTRO = DIR_DATOS / "contaflow.log"


def asegurar_flujos() -> None:
    """Garantiza que sys.stdout y sys.stderr existan.

    PyInstaller en modo ventana (console=False) los deja en None, porque el
    ejecutable no tiene consola asociada. Cualquier librería que escriba —o
    que consulte isatty(), como el formateador de logs de uvicorn— falla con
    «'NoneType' object has no attribute 'isatty'». Se redirigen a un archivo
    de registro para no perder los mensajes.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        destino = open(RUTA_REGISTRO, "a", encoding="utf-8", buffering=1)
    except OSError:
        destino = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = destino
    if sys.stderr is None:
        sys.stderr = destino


asegurar_flujos()


def puerto_disponible(host: str, puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, puerto))
            return True
        except OSError:
            return False


def buscar_puerto(host: str, inicial: int) -> int:
    for puerto in range(inicial, inicial + 40):
        if puerto_disponible(host, puerto):
            return puerto
    raise RuntimeError("No hay puertos libres para iniciar el servidor.")


class Servidor:
    """Servidor uvicorn corriendo en un hilo aparte."""

    def __init__(self, host: str, puerto: int):
        from contaflow.app import app

        self.url = f"http://{host}:{puerto}"
        # log_config=None evita que uvicorn instale su propio formateador con
        # colores, que depende de sys.stdout.isatty() y no funciona sin consola.
        config = uvicorn.Config(
            app, host=host, port=puerto, log_level="warning",
            access_log=False, log_config=None, use_colors=False,
        )
        self._servidor = uvicorn.Server(config)
        self._hilo = threading.Thread(target=self._servidor.run, daemon=True)

    def iniciar(self) -> None:
        self._hilo.start()
        for _ in range(120):  # hasta 12 s esperando a que levante
            if getattr(self._servidor, "started", False):
                return
            time.sleep(0.1)

    def detener(self) -> None:
        self._servidor.should_exit = True
        self._hilo.join(timeout=5)


def ventana_control(servidor: Servidor) -> bool:
    """Ventana mínima con Tkinter.

    Devuelve False si no se pudo abrir (Tkinter ausente, sin sesión de
    escritorio, servidor X inaccesible…). En ese caso el llamador mantiene
    vivo el proceso sin interfaz, para no derribar el servidor.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
    except Exception as exc:  # ImportError, TclError, …
        print(f"No se pudo abrir la ventana de control ({exc}).")
        return False

    raiz.title(f"{APP_NAME} {APP_VERSION}")
    raiz.geometry("430x250")
    raiz.resizable(False, False)
    raiz.configure(bg="#1f3864")

    tk.Label(raiz, text=APP_NAME, font=("Segoe UI", 22, "bold"),
             fg="white", bg="#1f3864").pack(pady=(24, 0))
    tk.Label(raiz, text="Sistema contable chileno multiempresa",
             font=("Segoe UI", 9), fg="#a8b8d8", bg="#1f3864").pack()
    tk.Label(raiz, text=f"Servidor activo en {servidor.url}",
             font=("Segoe UI", 9), fg="#7fd6c4", bg="#1f3864").pack(pady=(14, 0))
    tk.Label(raiz, text=f"Datos: {DIR_DATOS}", font=("Segoe UI", 7.5),
             fg="#8fa2c4", bg="#1f3864", wraplength=390).pack(pady=(2, 0))

    marco = tk.Frame(raiz, bg="#1f3864")
    marco.pack(pady=18)
    tk.Button(marco, text="Abrir ContaFlow", font=("Segoe UI", 10, "bold"),
              bg="#0d9488", fg="white", relief="flat", padx=18, pady=7,
              command=lambda: webbrowser.open(servidor.url)).pack(side="left", padx=6)

    def salir():
        if messagebox.askokcancel("Salir", "¿Cerrar ContaFlow? Se detendrá el servidor local."):
            servidor.detener()
            raiz.destroy()

    tk.Button(marco, text="Salir", font=("Segoe UI", 10), bg="#33507f",
              fg="white", relief="flat", padx=18, pady=7, command=salir).pack(side="left", padx=6)

    tk.Label(raiz, text="Cierra esta ventana sólo cuando termines de trabajar.",
             font=("Segoe UI", 7.5), fg="#8fa2c4", bg="#1f3864").pack(side="bottom", pady=8)

    raiz.protocol("WM_DELETE_WINDOW", salir)
    raiz.mainloop()
    return True


def informar_error(exc: BaseException) -> None:
    """Muestra un error de arranque de forma legible y lo deja en el registro.

    Sin esto, un fallo temprano en el ejecutable sólo produce el críptico
    «Failed to execute script 'run'» de PyInstaller.
    """
    detalle = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        with open(RUTA_REGISTRO, "a", encoding="utf-8") as registro:
            registro.write(f"\n--- Error de arranque ---\n{detalle}\n")
    except OSError:
        pass

    mensaje = (
        f"{APP_NAME} no pudo iniciarse.\n\n"
        f"{type(exc).__name__}: {exc}\n\n"
        f"El detalle quedó en:\n{RUTA_REGISTRO}"
    )
    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(f"{APP_NAME} — error de arranque", mensaje)
        raiz.destroy()
    except Exception:
        print(mensaje, file=sys.stderr)


def main() -> int:
    puerto = buscar_puerto(HOST, PUERTO)
    servidor = Servidor(HOST, puerto)

    print(f"{APP_NAME} {APP_VERSION}")
    print(f"Datos en: {DIR_DATOS}")
    print("Iniciando servidor local...")
    servidor.iniciar()
    print(f"Listo. Abre {servidor.url} en tu navegador.")

    webbrowser.open(servidor.url)

    if not ventana_control(servidor):
        # Sin ventana: el servidor sigue en pie y se cierra con Ctrl+C
        # (o cerrando la consola).
        print(f"ContaFlow sigue activo en {servidor.url}.")
        print("Presiona Ctrl+C para cerrarlo.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            servidor.detener()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - último recurso del ejecutable
        informar_error(exc)
        sys.exit(1)
