from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time

class MockLambdaHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Le decimos a la CLI que todo salió bien (HTTP 200)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        # Simulamos un pequeño retraso de "procesamiento de IA"
        time.sleep(1.5)
        
        # Simulamos la respuesta perfecta de Claude 3 Haiku
        response = {
            "tickets": [
                {
                    "title": "Modelado de BD para Rutinas",
                    "description": "Diseñar esquema para catálogo de ejercicios y series.",
                    "acceptance_criteria": [
                        "Crear tabla de rutinas en la base de datos",
                        "Definir relaciones con el catálogo de ejercicios"
                    ],
                    "priority": "high",
                    "story_points": 5,
                    "assignee": "Galo"
                },
                {
                    "title": "Maquetación UI de Atleta",
                    "description": "Crear vistas en la PWA para mostrar la rutina diaria.",
                    "acceptance_criteria": [
                        "Implementar la vista responsiva",
                        "Integrar el botón para marcar ejercicios completados"
                    ],
                    "priority": "medium",
                    "story_points": 8,
                    "assignee": "Andrea Pineda"
                },
                {
                    "title": "Dockerización del Módulo",
                    "description": "Actualizar docker-compose con los nuevos servicios.",
                    "acceptance_criteria": [
                        "Verificar que los volúmenes de la base de datos persistan",
                        "Asegurar la conexión entre la API y la BD en el entorno local"
                    ],
                    "priority": "high",
                    "story_points": 3,
                    "assignee": "Molina"
                }
            ],
            "metadata": {
                "model_id": "mock-claude-3-haiku",
                "region": "localhost",
                "input_tokens": 150,
                "output_tokens": 85,
                "latency_ms": 1500
            }
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))

    # Para apagar los logs molestos del servidor en la consola
    def log_message(self, format, *args):
        pass

print("🚀 Servidor Mock simulando AWS Lambda ejecutándose en http://localhost:8000")
HTTPServer(('localhost', 8000), MockLambdaHandler).serve_forever()