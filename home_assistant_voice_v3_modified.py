import sys
import os
import json
import threading
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import requests
import io
import wave
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QSystemTrayIcon, QMenu, QAction, QCheckBox,
                             QMessageBox, QComboBox, QDialog, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QDialogButtonBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import QUrl

class ListeningPopup(QWidget):
    """Popup central care afișează 'Ascult...' """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.init_ui()
        
    def init_ui(self):
        """Inițializează interfața popup-ului"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Container cu background
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: rgba(33, 150, 243, 220);
                border-radius: 20px;
                border: 3px solid rgba(255, 255, 255, 180);
            }
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(40, 30, 40, 30)
        
        # Label "Ascult..."
        self.label = QLabel("🎤 Ascult...")
        self.label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setStyleSheet("color: white; background: transparent; border: none;")
        container_layout.addWidget(self.label)
        
        layout.addWidget(container)
        
        # Setează dimensiunea fixă
        self.setFixedSize(300, 150)
        
    def show_centered(self):
        """Afișează popup-ul centrat pe ecran"""
        # Obține geometria ecranului
        screen = QApplication.desktop().screenGeometry()
        
        # Calculează poziția centrată
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        
        self.move(x, y)
        self.show()
        
        # Animație de fade-in (opțional)
        self.setWindowOpacity(0)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()

class LocalCommandEditor(QDialog):
    """Dialog pentru editarea comenzilor vocale locale"""
    
    def __init__(self, parent=None, commands=None):
        super().__init__(parent)
        self.commands = commands if commands else []
        self.init_ui()
        self.load_commands()
        
    def init_ui(self):
        self.setWindowTitle('Editor Comenzi Vocale Locale')
        self.setGeometry(200, 200, 600, 400)
        
        layout = QVBoxLayout(self)
        
        # Instrucțiuni
        info_label = QLabel(
            'Definește comenzi vocale locale care se execută instant, fără internet.\n'
            'Exemplu: "aprinde lumina" → service: light.turn_on, entity: light.living_room'
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet('padding: 10px; background-color: #e3f2fd; border-radius: 4px;')
        layout.addWidget(info_label)
        
        # Tabel comenzi
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Comandă Vocală', 'Service', 'Entity ID', 'Acțiuni'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)
        
        # Butoane pentru adăugare
        button_layout = QHBoxLayout()
        add_btn = QPushButton('➕ Adaugă Comandă Nouă')
        add_btn.clicked.connect(self.add_command)
        button_layout.addWidget(add_btn)
        layout.addLayout(button_layout)
        
        # Butoane OK/Cancel
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def load_commands(self):
        """Încarcă comenzile în tabel"""
        self.table.setRowCount(len(self.commands))
        for i, cmd in enumerate(self.commands):
            self.table.setItem(i, 0, QTableWidgetItem(cmd.get('phrase', '')))
            self.table.setItem(i, 1, QTableWidgetItem(cmd.get('service', '')))
            self.table.setItem(i, 2, QTableWidgetItem(cmd.get('entity_id', '')))
            
            # Buton ștergere
            delete_btn = QPushButton('🗑️')
            delete_btn.setMaximumWidth(40)
            delete_btn.clicked.connect(lambda checked, row=i: self.delete_command(row))
            self.table.setCellWidget(i, 3, delete_btn)
            
    def add_command(self):
        """Adaugă o comandă nouă"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(''))
        self.table.setItem(row, 1, QTableWidgetItem(''))
        self.table.setItem(row, 2, QTableWidgetItem(''))
        
        delete_btn = QPushButton('🗑️')
        delete_btn.setMaximumWidth(40)
        delete_btn.clicked.connect(lambda checked, r=row: self.delete_command(r))
        self.table.setCellWidget(row, 3, delete_btn)
        
    def delete_command(self, row):
        """Șterge o comandă"""
        self.table.removeRow(row)
        
    def get_commands(self):
        """Returnează lista de comenzi din tabel"""
        commands = []
        for row in range(self.table.rowCount()):
            phrase_item = self.table.item(row, 0)
            service_item = self.table.item(row, 1)
            entity_item = self.table.item(row, 2)
            
            if phrase_item and service_item:
                phrase = phrase_item.text().strip()
                service = service_item.text().strip()
                entity = entity_item.text().strip() if entity_item else ''
                
                if phrase and service:
                    commands.append({
                        'phrase': phrase.lower(),
                        'service': service,
                        'entity_id': entity
                    })
        return commands

class VoiceRecognitionThread(QThread):
    """Thread pentru recunoașterea vocală cu wake word și comenzi locale"""
    recognized_text = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    wake_word_detected = pyqtSignal()
    command_processed = pyqtSignal()  # Nou semnal pentru când comanda e procesată
    
    def __init__(self, device_index=None, wake_word="asistent", local_commands=None):
        super().__init__()
        self.running = False
        self.recognizer = sr.Recognizer()
        self.device_index = device_index
        self.sample_rate = 16000
        self.channels = 1
        self.wake_word = wake_word.lower()
        self.local_commands = local_commands if local_commands else []
        self.waiting_for_wake_word = True
        self.energy_threshold = 300  # Prag pentru detectarea sunetului
        
    def run(self):
        """Rulează bucla de recunoaștere vocală cu wake word"""
        self.status_signal.emit(f"🔊 Aștept cuvântul de trezire: '{self.wake_word}'")
        
        while self.running:
            try:
                if self.waiting_for_wake_word:
                    self.status_signal.emit(f"💤 Aștept '{self.wake_word}'...")
                else:
                    self.status_signal.emit("🎤 Ascult comenzi...")
                
                # Înregistrare audio cu sounddevice
                duration = 4 if self.waiting_for_wake_word else 5
                recording = sd.rec(
                    int(duration * self.sample_rate),
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='int16',
                    device=self.device_index
                )
                
                # Așteaptă sfârșitul înregistrării
                sd.wait()
                
                # Verifică dacă există sunet (nu doar tăcere)
                if np.abs(recording).max() < self.energy_threshold:
                    continue
                
                # Convertește la format AudioData pentru speech_recognition
                audio_data = self.numpy_to_audiodata(recording)
                
                self.status_signal.emit("🔄 Procesez...")
                
                try:
                    text = self.recognizer.recognize_google(audio_data, language='ro-RO')
                    text_lower = text.lower().strip()
                    
                    if self.waiting_for_wake_word:
                        # Verifică dacă conține wake word
                        if self.wake_word in text_lower:
                            self.waiting_for_wake_word = False
                            self.wake_word_detected.emit()
                            self.status_signal.emit("✅ Wake word detectat! Vorbește acum...")
                            continue
                    else:
                        # Procesează comanda
                        if text.strip():
                            # Verifică comenzile locale
                            local_match = self.check_local_commands(text_lower)
                            if local_match:
                                self.recognized_text.emit(f"LOCAL:{json.dumps(local_match)}")
                            else:
                                self.recognized_text.emit(text)
                            
                            # Revine la așteptarea wake word
                            self.waiting_for_wake_word = True
                            self.command_processed.emit()  # Emite semnal că s-a procesat comanda
                            
                except sr.UnknownValueError:
                    if not self.waiting_for_wake_word:
                        self.error_signal.emit("Nu am înțeles...")
                        self.waiting_for_wake_word = True
                        self.command_processed.emit()
                except sr.RequestError as e:
                    self.error_signal.emit(f"Eroare serviciu: {str(e)}")
                    if not self.waiting_for_wake_word:
                        self.waiting_for_wake_word = True
                        self.command_processed.emit()
                        
            except Exception as e:
                self.error_signal.emit(f"Eroare: {str(e)}")
                if not self.waiting_for_wake_word:
                    self.waiting_for_wake_word = True
                    self.command_processed.emit()
                    
    def check_local_commands(self, text):
        """Verifică dacă textul corespunde unei comenzi locale"""
        for cmd in self.local_commands:
            if cmd['phrase'] in text:
                return cmd
        return None
        
    def numpy_to_audiodata(self, recording):
        """Convertește numpy array la AudioData pentru speech_recognition"""
        # Convertește int16 la bytes
        audio_bytes = recording.tobytes()
        
        # Creează un buffer WAV în memorie
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 2 bytes pentru int16
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_bytes)
        
        # Resetează pointer-ul la început
        wav_buffer.seek(0)
        
        # Creează AudioData
        with sr.AudioFile(wav_buffer) as source:
            audio_data = self.recognizer.record(source)
            
        return audio_data
        
    def stop(self):
        """Oprește thread-ul"""
        self.running = False

class HomeAssistantVoiceApp(QMainWindow):
    """Aplicația principală PyQt5"""
    
    def __init__(self):
        super().__init__()
        self.config_file = Path.home() / '.ha_voice_config.json'
        self.local_commands = []
        self.wake_word = "asistent"
        self.recognition_thread = None
        self.listening_popup = None  # Popup pentru "Ascult..."
        self.notification_sound = None  # Sunet de notificare
        self.init_ui()
        self.init_tray()
        self.load_audio_devices()
        self.load_config()
        self.init_notification_sound()
        
    def init_notification_sound(self):
        """Inițializează sunetul de notificare pentru wake word"""
        try:
            self.notification_sound = QSoundEffect()
            
            # Verifică dacă există un fișier personalizat
            custom_sound_file = Path.home() / '.ha_voice_notification_custom.wav'
            default_sound_file = Path.home() / '.ha_voice_notification.wav'
            
            if custom_sound_file.exists():
                # Folosește sunetul personalizat
                self.log_message("🔔 Folosesc sunet personalizat de notificare", "#2196F3")
                sound_file = custom_sound_file
            else:
                # Generează sunetul implicit doar dacă nu există
                if not default_sound_file.exists():
                    # Generează un ton de 800Hz pentru 0.2 secunde
                    sample_rate = 22050
                    duration = 0.2
                    frequency = 800
                    
                    # Generează sinusoidă
                    t = np.linspace(0, duration, int(sample_rate * duration))
                    wave_data = np.sin(2 * np.pi * frequency * t)
                    
                    # Aplicare fade-out pentru a evita click-uri
                    fade_samples = int(sample_rate * 0.05)
                    wave_data[-fade_samples:] *= np.linspace(1, 0, fade_samples)
                    
                    # Convertește la int16
                    wave_data = (wave_data * 32767).astype(np.int16)
                    
                    # Salvează în fișier
                    with wave.open(str(default_sound_file), 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(sample_rate)
                        wav_file.writeframes(wave_data.tobytes())
                
                sound_file = default_sound_file
            
            # Încarcă sunetul
            self.notification_sound.setSource(QUrl.fromLocalFile(str(sound_file)))
            self.notification_sound.setVolume(0.5)  # 50% volum
            
        except Exception as e:
            print(f"Eroare la inițializarea sunetului: {e}")
            self.notification_sound = None
        
    def init_ui(self):
        """Inițializează interfața"""
        self.setWindowTitle('Home Assistant Voice Control - Romanian')
        self.setGeometry(100, 100, 900, 700)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Setări conexiune
        settings_group = QWidget()
        settings_layout = QVBoxLayout(settings_group)
        
        # Header
        header = QLabel('🏠 Home Assistant Voice Control')
        header.setStyleSheet('font-size: 18px; font-weight: bold; color: #2196F3; padding: 10px;')
        settings_layout.addWidget(header)
        
        # URL Home Assistant
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel('URL Home Assistant:'))
        self.ha_url_input = QLineEdit()
        self.ha_url_input.setPlaceholderText('http://homeassistant.local:8123')
        url_layout.addWidget(self.ha_url_input)
        settings_layout.addLayout(url_layout)
        
        # Token
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel('Long-Lived Access Token:'))
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setPlaceholderText('Introdu token-ul din Home Assistant')
        token_layout.addWidget(self.token_input)
        settings_layout.addLayout(token_layout)
        
        # Wake Word
        wake_layout = QHBoxLayout()
        wake_layout.addWidget(QLabel('Cuvânt de trezire:'))
        self.wake_word_input = QLineEdit()
        self.wake_word_input.setText('asistent')
        self.wake_word_input.setPlaceholderText('Ex: asistent, ok nabu, hey computer')
        wake_layout.addWidget(self.wake_word_input)
        settings_layout.addLayout(wake_layout)
        
        # Device audio
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel('Microfon:'))
        self.device_combo = QComboBox()
        device_layout.addWidget(self.device_combo)
        settings_layout.addLayout(device_layout)
        
        # Comenzi locale
        local_cmd_layout = QHBoxLayout()
        self.edit_commands_btn = QPushButton('⚙️ Editează Comenzi Locale')
        self.edit_commands_btn.clicked.connect(self.open_command_editor)
        local_cmd_layout.addWidget(self.edit_commands_btn)
        local_cmd_layout.addStretch()
        settings_layout.addLayout(local_cmd_layout)
        
        # Checkbox-uri opțiuni
        options_layout = QHBoxLayout()
        self.autostart_checkbox = QCheckBox('Pornire automată')
        self.minimize_to_tray_checkbox = QCheckBox('Minimizează în tray la pornire')
        options_layout.addWidget(self.autostart_checkbox)
        options_layout.addWidget(self.minimize_to_tray_checkbox)
        options_layout.addStretch()
        settings_layout.addLayout(options_layout)
        
        # Butoane control
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton('💾 Salvează Configurația')
        self.save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_btn)
        
        self.start_btn = QPushButton('▶️ Pornește Ascultarea')
        self.start_btn.clicked.connect(self.start_listening)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton('⏹️ Oprește')
        self.stop_btn.clicked.connect(self.stop_listening)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        settings_layout.addLayout(button_layout)
        layout.addWidget(settings_group)
        
        # Status
        self.status_label = QLabel('Status: Inactiv')
        self.status_label.setStyleSheet('padding: 5px; background-color: #f5f5f5; border-radius: 3px;')
        layout.addWidget(self.status_label)
        
        # Log
        log_label = QLabel('📋 Log activitate:')
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet('''
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: "Consolas", "Monaco", monospace;
                font-size: 11px;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 5px;
            }
        ''')
        layout.addWidget(self.log_text)
        
        # Setări stil general
        self.setStyleSheet('''
            QMainWindow {
                background-color: #fafafa;
            }
            QPushButton {
                padding: 8px 15px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QComboBox {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
        ''')
        
    def init_tray(self):
        """Inițializează system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.create_tray_icon())
        
        # Meniu tray
        tray_menu = QMenu()
        
        show_action = QAction("Arată fereastra", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Ieșire", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
        
    def create_tray_icon(self):
        """Creează iconița pentru system tray"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fundal circular
        painter.setBrush(QColor(33, 150, 243))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        
        # Text
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont('Arial', 20, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, '🎤')
        
        painter.end()
        
        return QIcon(pixmap)
        
    def tray_icon_activated(self, reason):
        """Handler pentru click pe tray icon"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()
            
    def show_window(self):
        """Arată fereastra"""
        self.show()
        self.activateWindow()
        
    def quit_app(self):
        """Închide aplicația"""
        if self.recognition_thread and self.recognition_thread.isRunning():
            self.stop_listening()
        QApplication.quit()
        
    def closeEvent(self, event):
        """Override pentru a minimiza în tray în loc de a închide"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "HA Voice Control",
            "Aplicația rulează în fundal. Click dreapta pe icon pentru opțiuni.",
            QSystemTrayIcon.Information,
            2000
        )
        
    def load_audio_devices(self):
        """Încarcă dispozitivele audio disponibile"""
        try:
            devices = sd.query_devices()
            self.device_combo.clear()
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    self.device_combo.addItem(f"{device['name']}", i)
                    
        except Exception as e:
            self.log_message(f"⚠️ Eroare încărcare dispozitive: {str(e)}", "#ff9800")
            
    def open_command_editor(self):
        """Deschide editorul de comenzi locale"""
        editor = LocalCommandEditor(self, self.local_commands)
        if editor.exec_() == QDialog.Accepted:
            self.local_commands = editor.get_commands()
            self.log_message(f"✅ {len(self.local_commands)} comenzi locale configurate", "#4CAF50")
            
    def start_listening(self):
        """Pornește ascultarea vocală"""
        if not self.ha_url_input.text() or not self.token_input.text():
            QMessageBox.warning(self, "Configurare incompletă", 
                              "Te rog completează URL-ul și token-ul!")
            return
            
        # Actualizează wake word din input
        self.wake_word = self.wake_word_input.text().lower().strip()
        if not self.wake_word:
            self.wake_word = "asistent"
            
        device_index = self.device_combo.currentData()
        
        self.recognition_thread = VoiceRecognitionThread(
            device_index=device_index,
            wake_word=self.wake_word,
            local_commands=self.local_commands
        )
        self.recognition_thread.recognized_text.connect(self.handle_recognized_text)
        self.recognition_thread.error_signal.connect(self.handle_error)
        self.recognition_thread.status_signal.connect(self.update_status)
        self.recognition_thread.wake_word_detected.connect(self.on_wake_word_detected)
        self.recognition_thread.command_processed.connect(self.on_command_processed)
        
        self.recognition_thread.running = True
        self.recognition_thread.start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_message("✅ Ascultare pornită! Spune cuvântul de trezire...", "#4CAF50")
        
    def on_wake_word_detected(self):
        """Handler pentru când wake word-ul este detectat"""
        # Redă sunetul de notificare
        if self.notification_sound:
            try:
                self.notification_sound.play()
            except Exception as e:
                print(f"Eroare la redarea sunetului: {e}")
        
        # Afișează popup-ul "Ascult..."
        self.show_listening_popup()
        
    def on_command_processed(self):
        """Handler pentru când comanda a fost procesată"""
        # Ascunde popup-ul
        self.hide_listening_popup()
        
    def show_listening_popup(self):
        """Afișează popup-ul 'Ascult...' """
        if not self.listening_popup:
            self.listening_popup = ListeningPopup()
        self.listening_popup.show_centered()
        
    def hide_listening_popup(self):
        """Ascunde popup-ul 'Ascult...' """
        if self.listening_popup:
            self.listening_popup.hide()
        
    def stop_listening(self):
        """Oprește ascultarea"""
        if self.recognition_thread:
            self.recognition_thread.stop()
            self.recognition_thread.wait()
            
        # Ascunde popup-ul dacă e vizibil
        self.hide_listening_popup()
            
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Status: Oprit")
        self.log_message("⏹️ Ascultare oprită", "#ff9800")
        
    def handle_recognized_text(self, text):
        """Procesează textul recunoscut"""
        # Verifică dacă e comandă locală
        if text.startswith("LOCAL:"):
            cmd_data = json.loads(text[6:])
            self.execute_local_command(cmd_data)
        else:
            self.log_message(f"🗣️ Recunoscut: {text}", "#2196F3")
            self.send_to_home_assistant(text)
        
    def handle_error(self, error):
        """Afișează erori"""
        self.log_message(f"❌ {error}", "#ff6b6b")
        
    def send_to_home_assistant(self, text):
        """Trimite textul către API-ul Conversation de la Home Assistant"""
        url = f"{self.ha_url_input.text().rstrip('/')}/api/conversation/process"
        headers = {
            "Authorization": f"Bearer {self.token_input.text()}",
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "language": "ro"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', {}).get('speech', {}).get('plain', {}).get('speech', 'Comandă executată')
                self.log_message(f"✅ HA: {response_text}", "#4CAF50")
            else:
                self.log_message(f"❌ Eroare HTTP {response.status_code}", "#ff6b6b")
        except requests.exceptions.RequestException as e:
            self.log_message(f"❌ Eroare: {str(e)}", "#ff6b6b")
    
    def execute_local_command(self, cmd_data):
        """Execută o comandă locală direct prin API"""
        self.log_message(f"⚡ Comandă locală: {cmd_data['phrase']}", "#FF9800")
        
        # Construiește URL-ul pentru service call
        domain, service = cmd_data['service'].split('.')
        url = f"{self.ha_url_input.text().rstrip('/')}/api/services/{domain}/{service}"
        
        headers = {
            "Authorization": f"Bearer {self.token_input.text()}",
            "Content-Type": "application/json"
        }
        
        data = {}
        if cmd_data.get('entity_id'):
            data['entity_id'] = cmd_data['entity_id']
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=5)
            if response.status_code == 200:
                self.log_message(f"✅ Executat: {cmd_data['service']}", "#4CAF50")
            else:
                self.log_message(f"❌ Eroare HTTP {response.status_code}", "#ff6b6b")
        except Exception as e:
            self.log_message(f"❌ Eroare: {str(e)}", "#ff6b6b")
            
    def update_status(self, status):
        """Actualizează label-ul de status"""
        self.status_label.setText(f"Status: {status}")
        
    def log_message(self, message, color="#d4d4d4"):
        """Adaugă mesaj în log cu culoare"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color};">{message}</span>')
        
        # Auto-scroll la final
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def save_config(self):
        """Salvează configurația în fișier"""
        config = {
            'ha_url': self.ha_url_input.text(),
            'token': self.token_input.text(),
            'wake_word': self.wake_word_input.text(),
            'device_index': self.device_combo.currentData(),
            'device_name': self.device_combo.currentText(),
            'autostart': self.autostart_checkbox.isChecked(),
            'minimize_to_tray': self.minimize_to_tray_checkbox.isChecked(),
            'local_commands': self.local_commands
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Configurare autostart
            if self.autostart_checkbox.isChecked():
                self.enable_autostart()
            else:
                self.disable_autostart()
                
            self.log_message("✅ Configurație salvată!", "#4CAF50")
            QMessageBox.information(self, "Succes", "Configurația a fost salvată!")
        except Exception as e:
            self.log_message(f"❌ Eroare salvare: {str(e)}", "#ff6b6b")
            QMessageBox.critical(self, "Eroare", f"Nu pot salva:\n{str(e)}")
            
    def load_config(self):
        """Încarcă configurația din fișier"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                self.ha_url_input.setText(config.get('ha_url', ''))
                self.token_input.setText(config.get('token', ''))
                self.wake_word_input.setText(config.get('wake_word', 'asistent'))
                self.wake_word = config.get('wake_word', 'asistent')
                self.autostart_checkbox.setChecked(config.get('autostart', False))
                self.minimize_to_tray_checkbox.setChecked(config.get('minimize_to_tray', False))
                self.local_commands = config.get('local_commands', [])
                
                # Selectează dispozitivul salvat
                saved_device = config.get('device_name', '')
                if saved_device:
                    index = self.device_combo.findText(saved_device)
                    if index >= 0:
                        self.device_combo.setCurrentIndex(index)
                
                # Minimizează în tray dacă e configurat
                if config.get('minimize_to_tray', False):
                    QApplication.processEvents()
                    self.hide()
                    self.tray_icon.showMessage(
                        "HA Voice Control",
                        "Pornit minimizat în tray.",
                        QSystemTrayIcon.Information,
                        2000
                    )
                    
            except Exception as e:
                self.log_message(f"⚠️ Eroare încărcare: {str(e)}", "#ff9800")
                
    def enable_autostart(self):
        """Activează pornirea automată"""
        if sys.platform == 'win32':
            try:
                import winreg
                key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                
                python_exe = sys.executable.replace('python.exe', 'pythonw.exe')
                winreg.SetValueEx(key, 'HAVoiceControl', 0, winreg.REG_SZ, 
                                f'"{python_exe}" "{os.path.abspath(__file__)}"')
                winreg.CloseKey(key)
                self.log_message("✅ Autostart activat (Windows)", "#4CAF50")
            except Exception as e:
                self.log_message(f"❌ Eroare autostart: {str(e)}", "#ff6b6b")
        else:  # Linux
            autostart_dir = Path.home() / '.config' / 'autostart'
            autostart_dir.mkdir(parents=True, exist_ok=True)
            desktop_file = autostart_dir / 'ha-voice-control.desktop'
            
            content = f"""[Desktop Entry]
Type=Application
Name=HA Voice Control
Exec={sys.executable} {os.path.abspath(__file__)}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""
            try:
                desktop_file.write_text(content)
                self.log_message("✅ Autostart activat (Linux)", "#4CAF50")
            except Exception as e:
                self.log_message(f"❌ Eroare autostart: {str(e)}", "#ff6b6b")
                
    def disable_autostart(self):
        """Dezactivează pornirea automată"""
        if sys.platform == 'win32':
            try:
                import winreg
                key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, 'HAVoiceControl')
                winreg.CloseKey(key)
                self.log_message("✅ Autostart dezactivat", "#4CAF50")
            except:
                pass
        else:  # Linux
            desktop_file = Path.home() / '.config' / 'autostart' / 'ha-voice-control.desktop'
            if desktop_file.exists():
                desktop_file.unlink()
                self.log_message("✅ Autostart dezactivat", "#4CAF50")

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = HomeAssistantVoiceApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
