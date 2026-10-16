"""Servidor HTTP local para a telemetria da interface.

Por que existe: a ponte do pywebview cria uma thread nova por chamada e, para
devolver o resultado, monta delegates .NET via pythonnet. Com a interface
consultando 4x por segundo, isso virava uma corrida entre o coletor de lixo do
Python e o runtime .NET, e o processo morria com STATUS_BREAKPOINT (ver o
crash.log guardado no README).

Aqui a leitura de estado sai da ponte e vira `fetch` normal: nenhum delegate,
nenhum `evaluate_js`. A ponte fica so para as acoes do usuario, que sao raras.

Escuta apenas em 127.0.0.1 e exige um token sorteado no arranque, para que
outra pagina aberta na maquina nao consiga ler o estado do bot.
"""

import hmac
import json
import logging
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HOST = "127.0.0.1"


class _Handler(BaseHTTPRequestHandler):
    provider = None            # preenchido pelo start()
    token = ""

    # HTTP/1.1 mantem a conexao viva entre as consultas. Em HTTP/1.0 o navegador
    # reconectava a cada 250 ms e o servidor criava uma thread nova por
    # requisicao: milhares de threads e sockets por hora, so lixo para o coletor
    # recolher. Com keep-alive uma unica thread atende a interface inteira.
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def _local_authority(self, value, own_port=False):
        try:
            parsed = urlsplit(value)
            return (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")
                    and not parsed.username and not parsed.password and not parsed.path
                    and not parsed.query and not parsed.fragment
                    and parsed.port is not None
                    and (not own_port or parsed.port == self.server.server_address[1]))
        except ValueError:
            return False

    def _authorized(self, parameters):
        tokens = parameters.get("t", [])
        if len(tokens) != 1 or not tokens[0].isascii():
            return False
        if not hmac.compare_digest(tokens[0], self.token):
            return False
        if not self._local_authority("http://" + self.headers.get("Host", ""), own_port=True):
            return False
        origin = self.headers.get("Origin")
        return origin is None or self._local_authority(origin)

    def do_GET(self):                                  # noqa: N802
        request = urlsplit(self.path)
        parametros = parse_qs(request.query, keep_blank_values=True)
        if not self._authorized(parametros):
            self.send_error(403, "acesso recusado")
            return

        rota = request.path.removeprefix("/")
        if rota not in self.provider:
            self.send_error(404, "rota desconhecida")
            return

        try:
            corpo = json.dumps(self.provider[rota]()).encode("utf-8")
        except Exception:                       # noqa: BLE001
            logging.getLogger(__name__).exception("Falha na telemetria /%s", rota)
            self.send_error(500, "falha ao consultar estado")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        # a interface e servida por outra porta local: mesma maquina, origem diferente
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(corpo)
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, *_args):
        """Silencia o log padrao: seriam 4 linhas por segundo no console."""


def start(rotas):
    """Sobe o servidor numa porta livre. Devolve (base_url, token, servidor)."""
    token = secrets.token_urlsafe(16)

    handler = type("_BotHandler", (_Handler,), {"provider": rotas, "token": token})
    servidor = ThreadingHTTPServer((HOST, 0), handler)
    servidor.daemon_threads = True

    thread = threading.Thread(target=servidor.serve_forever, daemon=True,
                              name="telemetria")
    thread.start()

    porta = servidor.server_address[1]
    return f"http://{HOST}:{porta}", token, servidor
