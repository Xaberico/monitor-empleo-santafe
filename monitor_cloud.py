"""
Monitor de Empleo Santa Fe - Versión Cloud
Envía notificaciones por Telegram (más confiable que email en servicios gratuitos)
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import hashlib

class MonitorEmpleoCloud:
    def __init__(self):
        self.url_base = "https://www.santafe.gob.ar/simtyss/portalempleo/"
        self.url_busqueda = f"{self.url_base}ofertas/"
        self.archivo_estado = "empleos_anteriores.json"
        
        # Variables de entorno para configuración
        self.telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        self.email_destinatario = os.environ.get('EMAIL_DESTINATARIO', '')
        
        self.empleos_anteriores = self.cargar_estado()
    
    def cargar_estado(self):
        """Carga el estado anterior de empleos monitoreados"""
        try:
            if os.path.exists(self.archivo_estado):
                with open(self.archivo_estado, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error al cargar estado: {e}")
        return []
    
    def guardar_estado(self, empleos):
        """Guarda el estado actual de empleos"""
        try:
            with open(self.archivo_estado, 'w', encoding='utf-8') as f:
                json.dump(empleos, f, indent=2, ensure_ascii=False)
            print(f"Estado guardado: {len(empleos)} ofertas")
        except Exception as e:
            print(f"Error al guardar estado: {e}")
    
    def obtener_ofertas(self):
        """Obtiene las ofertas de empleo del portal"""
        ofertas = []
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            print(f"Consultando: {self.url_busqueda}")
            response = requests.get(self.url_busqueda, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Intentar múltiples selectores para encontrar ofertas
            elementos_ofertas = (
                soup.find_all('div', class_='oferta') or
                soup.find_all('div', class_='job-item') or
                soup.find_all('article') or
                soup.find_all('div', class_='card') or
                soup.find_all('li', class_='list-item')
            )
            
            print(f"Elementos encontrados: {len(elementos_ofertas)}")
            
            for elemento in elementos_ofertas:
                try:
                    # Buscar título
                    titulo = (
                        elemento.find(['h2', 'h3', 'h4', 'h5']) or
                        elemento.find('a', class_='titulo') or
                        elemento.find('strong')
                    )
                    
                    # Buscar empresa
                    empresa = elemento.find(
                        class_=['empresa', 'company', 'empleador', 'organismo']
                    )
                    
                    # Buscar ubicación
                    ubicacion = elemento.find(
                        class_=['ubicacion', 'location', 'localidad', 'lugar']
                    )
                    
                    # Buscar enlace
                    enlace = elemento.find('a', href=True)
                    
                    if titulo:  # Solo agregar si tiene al menos título
                        titulo_texto = titulo.get_text(strip=True)
                        empresa_texto = empresa.get_text(strip=True) if empresa else 'Gobierno de Santa Fe'
                        
                        oferta = {
                            'titulo': titulo_texto,
                            'empresa': empresa_texto,
                            'ubicacion': ubicacion.get_text(strip=True) if ubicacion else 'Santa Fe',
                            'enlace': self.construir_enlace(enlace),
                            'fecha_deteccion': datetime.now().isoformat(),
                            'hash': self.calcular_hash(titulo_texto, empresa_texto)
                        }
                        
                        ofertas.append(oferta)
                        
                except Exception as e:
                    print(f"Error procesando elemento: {e}")
                    continue
            
            print(f"Ofertas procesadas: {len(ofertas)}")
            
        except requests.exceptions.RequestException as e:
            print(f"Error en la petición HTTP: {e}")
        except Exception as e:
            print(f"Error inesperado: {e}")
        
        return ofertas
    
    def construir_enlace(self, elemento_enlace):
        """Construye la URL completa del enlace"""
        if not elemento_enlace:
            return self.url_base
        
        href = elemento_enlace.get('href', '')
        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return f"https://www.santafe.gob.ar{href}"
        else:
            return f"{self.url_base}{href}"
    
    def calcular_hash(self, titulo, empresa):
        """Calcula un hash único para una oferta"""
        texto = f"{titulo}{empresa}".lower().strip()
        return hashlib.md5(texto.encode()).hexdigest()
    
    def detectar_nuevas_ofertas(self, ofertas_actuales):
        """Detecta ofertas nuevas comparando con el estado anterior"""
        hashes_anteriores = {emp['hash'] for emp in self.empleos_anteriores}
        nuevas = [o for o in ofertas_actuales if o['hash'] not in hashes_anteriores]
        print(f"Nuevas ofertas detectadas: {len(nuevas)}")
        return nuevas
    
    def enviar_telegram(self, nuevas_ofertas):
        """Envía notificación por Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("Telegram no configurado. Saltando notificación.")
            return False
        
        try:
            mensaje = f"🔔 *Nuevas Ofertas de Empleo - Santa Fe*\n"
            mensaje += f"Se detectaron {len(nuevas_ofertas)} nueva(s) oferta(s)\n\n"
            
            for i, oferta in enumerate(nuevas_ofertas[:10], 1):  # Limitar a 10
                mensaje += f"{i}. *{oferta['titulo']}*\n"
                mensaje += f"   📍 {oferta['ubicacion']}\n"
                mensaje += f"   🏢 {oferta['empresa']}\n"
                mensaje += f"   🔗 [Ver oferta]({oferta['enlace']})\n\n"
            
            if len(nuevas_ofertas) > 10:
                mensaje += f"... y {len(nuevas_ofertas) - 10} ofertas más.\n"
            
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': mensaje,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            print("✓ Notificación Telegram enviada exitosamente")
            return True
            
        except Exception as e:
            print(f"Error al enviar Telegram: {e}")
            return False
    
    def generar_resumen(self, nuevas_ofertas, ofertas_totales):
        """Genera un resumen del estado actual"""
        print("\n" + "="*70)
        print(f"RESUMEN DE MONITOREO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        print(f"Ofertas totales en el portal: {len(ofertas_totales)}")
        print(f"Ofertas nuevas detectadas: {len(nuevas_ofertas)}")
        print(f"Ofertas ya conocidas: {len(self.empleos_anteriores)}")
        
        if nuevas_ofertas:
            print("\nNUEVAS OFERTAS:")
            for i, oferta in enumerate(nuevas_ofertas, 1):
                print(f"\n{i}. {oferta['titulo']}")
                print(f"   Empresa: {oferta['empresa']}")
                print(f"   Ubicación: {oferta['ubicacion']}")
                print(f"   Link: {oferta['enlace']}")
        else:
            print("\nNo se detectaron nuevas ofertas en esta ejecución.")
        
        print("\n" + "="*70 + "\n")
    
    def ejecutar(self):
        """Ejecuta una única verificación (ideal para ejecuciones programadas)"""
        print("Iniciando verificación de ofertas de empleo...")
        print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Obtener ofertas actuales
        ofertas_actuales = self.obtener_ofertas()
        
        if not ofertas_actuales:
            print("⚠️  No se pudieron obtener ofertas. Verificar conectividad o estructura del sitio.")
            return
        
        # Detectar nuevas ofertas
        nuevas_ofertas = self.detectar_nuevas_ofertas(ofertas_actuales)
        
        # Generar resumen
        self.generar_resumen(nuevas_ofertas, ofertas_actuales)
        
        # Enviar notificaciones si hay nuevas ofertas
        if nuevas_ofertas:
            self.enviar_telegram(nuevas_ofertas)
        
        # Guardar estado actualizado
        self.guardar_estado(ofertas_actuales)
        
        print("✓ Verificación completada")

if __name__ == "__main__":
    monitor = MonitorEmpleoCloud()
    monitor.ejecutar()
