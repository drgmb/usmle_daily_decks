import json
import os
from datetime import datetime
from aqt import mw, gui_hooks
from aqt.qt import *
from aqt.utils import showInfo, tooltip
from aqt.operations import QueryOp

# Configurações de persistência
ADDON_NAME = "usmle_daily_decks"
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"error_tag": "gmberro", "auto_rebuild": False, "last_build_day": -1}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f)

class FilteredDeckManager(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.mw = parent
        self.setWindowTitle("USMLE Manager")
        self.config = load_config()
        self.date_str = datetime.now().strftime("%d/%m/%y")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel(f"<b>Date: {self.date_str}</b>"))
        layout.addWidget(QLabel("Error Tag:"))
        self.tag_input = QLineEdit(self.config["error_tag"])
        layout.addWidget(self.tag_input)

        # Checkbox de reconstrução automática
        self.auto_rebuild_checkbox = QCheckBox("Automatic daily rebuild")
        self.auto_rebuild_checkbox.setChecked(self.config.get("auto_rebuild", False))
        self.auto_rebuild_checkbox.stateChanged.connect(self.on_auto_rebuild_toggled)
        layout.addWidget(self.auto_rebuild_checkbox)

        # Barra de progresso (inicialmente oculta)
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.hide()
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3498db;
                border-radius: 5px;
                text-align: center;
                background-color: #ecf0f1;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Botões
        self.btn_build = QPushButton("Build Daily Decks")
        self.btn_build.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; min-height: 30px;")
        self.btn_build.clicked.connect(self.build_decks)
        layout.addWidget(self.btn_build)

        self.btn_empty = QPushButton("Clear & Remove Decks")
        self.btn_empty.setStyleSheet("background-color: #e74c3c; color: white; min-height: 30px;")
        self.btn_empty.clicked.connect(self.empty_decks)
        layout.addWidget(self.btn_empty)

        layout.addStretch()

        credit = QLabel('<a href="https://github.com/drgmb" style="color: #888888; text-decoration: none; font-size: 10px;">crafted by drgmb</a>')
        credit.setAlignment(Qt.AlignmentFlag.AlignRight)
        credit.setOpenExternalLinks(True)
        credit.setToolTip("github.com/drgmb")
        layout.addWidget(credit)

        self.setLayout(layout)

    def show_progress(self, show=True):
        """Mostra ou oculta a barra de progresso"""
        if show:
            self.progress_label.show()
            self.progress_bar.show()
            self.btn_build.setEnabled(False)
            self.btn_empty.setEnabled(False)
            self.tag_input.setEnabled(False)
        else:
            self.progress_label.hide()
            self.progress_bar.hide()
            self.btn_build.setEnabled(True)
            self.btn_empty.setEnabled(True)
            self.tag_input.setEnabled(True)

    def update_progress(self, value, text=""):
        """Atualiza o valor e texto da barra de progresso"""
        self.progress_bar.setValue(value)
        if text:
            self.progress_label.setText(text)

    def on_auto_rebuild_toggled(self, state):
        self.config["auto_rebuild"] = (state == Qt.CheckState.Checked.value)
        save_config(self.config)

    def build_decks(self):
        error_tag = self.tag_input.text().strip()
        self.config["error_tag"] = error_tag
        save_config(self.config)

        # Lista ordenada de decks para manter a ordem de criação
        decks_to_create = [
            (f"00 - {error_tag} + HY (1,2,3) [{self.date_str}]",
             f"tag:*{error_tag} (tag:*1-HighYield or tag:*2-RelativelyHighYield or tag:*3-HighYield-temporary) is:due"),

            (f"01 - HY Cards [{self.date_str}]",
             f"tag:*1-HighYield (is:learn or is:due) prop:due<=0"),

            (f"02 - Relative HY Cards [{self.date_str}]",
             f"tag:*2-RelativelyHighYield (is:learn or is:due) prop:due<=0"),

            (f"03 - Temporary HY Cards [{self.date_str}]",
             f"tag:*3-HighYield-temporary (is:learn or is:due) prop:due<=0"),

            (f"05 - NEW + {error_tag} + HY (1,2,3) [{self.date_str}]",
             f"tag:*{error_tag} (tag:*1-HighYield or tag:*2-RelativelyHighYield or tag:*3-HighYield-temporary) is:new")
        ]

        # Mostrar barra de progresso
        self.show_progress(True)
        self.update_progress(0, "Starting deck creation...")

        def create_decks_op(col):
            """Operação que roda em background"""
            total_decks = len(decks_to_create)

            # Criar decks na ordem especificada
            for idx, (name, query) in enumerate(decks_to_create, 1):
                # Atualizar progresso
                progress = int((idx - 0.5) / total_decks * 100)
                mw.taskman.run_on_main(
                    lambda p=progress, n=name: self.update_progress(p, f"Creating: {n[:30]}...")
                )

                # Criar deck filtrado
                did = col.decks.new_filtered(name)
                deck = col.decks.get(did)

                # Configurar a busca
                deck['terms'][0][0] = query
                deck['terms'][0][1] = 999
                deck['resched'] = True

                col.decks.save(deck)
                col.sched.rebuild_filtered_deck(did)

                # Atualizar progresso após conclusão
                progress = int(idx / total_decks * 100)
                mw.taskman.run_on_main(
                    lambda p=progress, i=idx, t=total_decks: self.update_progress(p, f"Deck {i}/{t} created!")
                )

            return len(decks_to_create)

        def on_success(count):
            """Callback quando a operação termina com sucesso"""
            self.update_progress(100, "Finishing...")

            # CRÍTICO: Atualizar a interface do Anki
            mw.reset()

            # Atualizar a tela de decks se estiver aberta
            if hasattr(mw, 'deckBrowser'):
                mw.deckBrowser.refresh()

            # Salvar last_build_day para evitar auto-rebuild no mesmo dia
            if mw.col is not None:
                self.config["last_build_day"] = mw.col.sched.today
                save_config(self.config)

            # Ocultar barra de progresso
            self.show_progress(False)

            showInfo(f"{count} decks created successfully!")
            self.accept()

        def on_failure(exc):
            """Callback em caso de erro"""
            self.show_progress(False)
            showInfo(f"Error creating decks: {str(exc)}")

        # Executar operação usando QueryOp (padrão do Anki moderno)
        op = QueryOp(
            parent=self,
            op=create_decks_op,
            success=on_success
        )
        op.failure(on_failure)
        op.run_in_background()

    def empty_decks(self):
        prefixes = ("00 -", "01 -", "02 -", "03 -", "05 -")

        # Mostrar barra de progresso
        self.show_progress(True)
        self.update_progress(0, "Looking for decks to remove...")

        def remove_decks_op(col):
            """Operação que roda em background"""
            all_decks = col.decks.all_names_and_ids()
            count = 0
            deck_ids = []

            # Coletar IDs dos decks a serem removidos
            mw.taskman.run_on_main(
                lambda: self.update_progress(20, "Identifying decks...")
            )

            for d in all_decks:
                if any(d.name.startswith(p) for p in prefixes):
                    deck_ids.append(d.id)
                    count += 1

            if count == 0:
                mw.taskman.run_on_main(
                    lambda: self.update_progress(100, "No decks found")
                )
                return 0

            # Remover os decks
            total = len(deck_ids)
            for idx, did in enumerate(deck_ids, 1):
                progress = int(20 + (idx / total * 70))
                mw.taskman.run_on_main(
                    lambda p=progress, i=idx, t=total: self.update_progress(p, f"Removing deck {i}/{t}...")
                )
                col.decks.remove([did])

            mw.taskman.run_on_main(
                lambda: self.update_progress(90, "Finishing removal...")
            )

            return count

        def on_success(count):
            """Callback quando a operação termina com sucesso"""
            self.update_progress(100, "Done!")

            # CRÍTICO: Atualizar a interface do Anki
            mw.reset()

            # Atualizar a tela de decks se estiver aberta
            if hasattr(mw, 'deckBrowser'):
                mw.deckBrowser.refresh()

            # Ocultar barra de progresso
            self.show_progress(False)

            if count > 0:
                showInfo(f"{count} decks removed.")
            else:
                showInfo("No USMLE decks found to remove.")

            self.accept()

        def on_failure(exc):
            """Callback em caso de erro"""
            self.show_progress(False)
            showInfo(f"Error removing decks: {str(exc)}")

        # Executar operação usando QueryOp
        op = QueryOp(
            parent=self,
            op=remove_decks_op,
            success=on_success
        )
        op.failure(on_failure)
        op.run_in_background()

def on_show_manager():
    dialog = FilteredDeckManager(mw)
    dialog.exec()

def maybe_auto_rebuild():
    config = load_config()
    if not config.get("auto_rebuild", False):
        return
    if mw.col is None:
        return
    today = mw.col.sched.today
    if config.get("last_build_day", -1) == today:
        return
    # Day changed: rebuild silently
    _run_auto_rebuild(today)

def _run_auto_rebuild(today):
    """Executa rebuild automático silencioso"""
    config = load_config()
    error_tag = config.get("error_tag", "gmberro")
    date_str = datetime.now().strftime("%d/%m/%y")
    prefixes = ("00 -", "01 -", "02 -", "03 -", "05 -")

    decks_to_create = [
        (f"00 - {error_tag} + HY (1,2,3) [{date_str}]",
         f"tag:*{error_tag} (tag:*1-HighYield or tag:*2-RelativelyHighYield or tag:*3-HighYield-temporary) is:due"),

        (f"01 - HY Cards [{date_str}]",
         f"tag:*1-HighYield (is:learn or is:due) prop:due<=0"),

        (f"02 - Relative HY Cards [{date_str}]",
         f"tag:*2-RelativelyHighYield (is:learn or is:due) prop:due<=0"),

        (f"03 - Temporary HY Cards [{date_str}]",
         f"tag:*3-HighYield-temporary (is:learn or is:due) prop:due<=0"),

        (f"05 - NEW + {error_tag} + HY (1,2,3) [{date_str}]",
         f"tag:*{error_tag} (tag:*1-HighYield or tag:*2-RelativelyHighYield or tag:*3-HighYield-temporary) is:new")
    ]

    def remove_decks_op(col):
        """Remove decks existentes"""
        all_decks = col.decks.all_names_and_ids()
        deck_ids = []
        for d in all_decks:
            if any(d.name.startswith(p) for p in prefixes):
                deck_ids.append(d.id)
        for did in deck_ids:
            col.decks.remove([did])
        return len(deck_ids)

    def create_decks_op(col):
        """Cria novos decks"""
        for name, query in decks_to_create:
            did = col.decks.new_filtered(name)
            deck = col.decks.get(did)
            deck['terms'][0][0] = query
            deck['terms'][0][1] = 999
            deck['resched'] = True
            col.decks.save(deck)
            col.sched.rebuild_filtered_deck(did)
        return len(decks_to_create)

    def combined_op(col):
        """Remove e recria decks"""
        remove_decks_op(col)
        return create_decks_op(col)

    def on_success(count):
        """Callback silencioso"""
        mw.reset()
        if hasattr(mw, 'deckBrowser'):
            mw.deckBrowser.refresh()
        # Salvar last_build_day
        config = load_config()
        config["last_build_day"] = today
        save_config(config)
        tooltip("USMLE: decks rebuilt automatically.")

    def on_failure(exc):
        """Falha silenciosa"""
        pass

    op = QueryOp(
        parent=mw,
        op=combined_op,
        success=on_success
    )
    op.failure(on_failure)
    op.run_in_background()

def inject_usmle_button():
    """Injeta o botão USMLE na toolbar com estilo idêntico aos existentes"""
    js_code = """
    (function() {
        // Remover botão anterior se existir
        const oldBtn = document.getElementById('usmle-decks-btn');
        if (oldBtn) oldBtn.remove();

        // Estratégia 1: Procurar por container com id específico
        let container = document.getElementById('top-right-btns');

        // Estratégia 2: Procurar buttons existentes e pegar o pai deles
        if (!container) {
            const existingButtons = document.querySelectorAll('button');
            for (let btn of existingButtons) {
                if (btn.textContent.includes('UWIds') || btn.textContent.includes('Add UW')) {
                    container = btn.parentElement;
                    break;
                }
            }
        }

        // Estratégia 3: Procurar por classes comuns de toolbar
        if (!container) {
            const possibleContainers = [
                document.querySelector('.top-right'),
                document.querySelector('.toolbar-right'),
                document.querySelector('[style*="position: absolute"][style*="right"]'),
                document.getElementById('topbutsOuter')
            ];

            for (let c of possibleContainers) {
                if (c) {
                    container = c;
                    break;
                }
            }
        }

        // Estratégia 4: Criar container se necessário
        if (!container) {
            container = document.createElement('div');
            container.id = 'usmle-custom-container';
            container.style.cssText = 'position: absolute; top: 10px; right: 10px; display: flex; gap: 8px; z-index: 9999;';
            document.body.appendChild(container);
        }

        // Copiar estilo de um botão existente
        const existingBtn = document.querySelector('button');
        let copiedStyles = {};

        if (existingBtn) {
            const computedStyle = window.getComputedStyle(existingBtn);
            copiedStyles = {
                backgroundColor: computedStyle.backgroundColor,
                color: computedStyle.color,
                border: computedStyle.border,
                borderRadius: computedStyle.borderRadius,
                padding: computedStyle.padding,
                fontSize: computedStyle.fontSize,
                fontWeight: computedStyle.fontWeight,
                fontFamily: computedStyle.fontFamily,
                cursor: computedStyle.cursor,
                transition: computedStyle.transition
            };
        }

        // Criar o botão
        const btn = document.createElement('button');
        btn.id = 'usmle-decks-btn';
        btn.textContent = 'USMLE Decks';

        // Aplicar estilos copiados ou usar fallback
        btn.style.cssText = `
            background-color: ${copiedStyles.backgroundColor || '#2c2c2c'};
            color: ${copiedStyles.color || '#ffffff'};
            border: ${copiedStyles.border || '2px solid #3c3c3c'};
            border-radius: ${copiedStyles.borderRadius || '5px'};
            padding: ${copiedStyles.padding || '8px 16px'};
            margin-left: 8px;
            font-weight: ${copiedStyles.fontWeight || 'bold'};
            font-size: ${copiedStyles.fontSize || '13px'};
            font-family: ${copiedStyles.fontFamily || 'inherit'};
            cursor: ${copiedStyles.cursor || 'pointer'};
            white-space: nowrap;
            transition: ${copiedStyles.transition || 'all 0.2s ease'};
        `;

        // Efeitos hover
        btn.onmouseover = function() {
            if (existingBtn) {
                this.style.opacity = '0.8';
                this.style.transform = 'scale(1.02)';
            } else {
                this.style.backgroundColor = '#3c3c3c';
            }
        };

        btn.onmouseout = function() {
            this.style.opacity = '1';
            this.style.transform = 'scale(1)';
            this.style.backgroundColor = copiedStyles.backgroundColor || '#2c2c2c';
        };

        btn.onclick = function() {
            pycmd('usmle:open');
        };

        // Adicionar o botão
        container.appendChild(btn);

        console.log('USMLE button added with copied styles');
    })();
    """

    if hasattr(mw, 'toolbar') and hasattr(mw.toolbar, 'web'):
        try:
            mw.toolbar.web.eval(js_code)
        except:
            pass

def on_state_did_change(new_state, old_state):
    """Reinjetar botão quando o estado da janela muda"""
    from aqt.qt import QTimer
    QTimer.singleShot(200, inject_usmle_button)

def handle_pycmd(handled, cmd, context):
    """Handler para comandos Python vindos do JavaScript"""
    if cmd == "usmle:open":
        on_show_manager()
        return True, None
    return handled

# Inicialização da UI do Anki
def init_addon():
    # Adicionar ao menu Tools (backup)
    action = QAction("⚡ USMLE Decks", mw)
    action.triggered.connect(on_show_manager)
    mw.form.menuTools.addAction(action)

    # Hooks para adicionar o botão
    gui_hooks.webview_did_receive_js_message.append(handle_pycmd)
    gui_hooks.state_did_change.append(on_state_did_change)

    # Hook para auto-rebuild ao abrir perfil
    gui_hooks.profile_did_open.append(maybe_auto_rebuild)

    # Tentar múltiplas vezes em diferentes momentos
    from aqt.qt import QTimer

    def try_inject():
        inject_usmle_button()

    gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(500, try_inject))
    gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(1000, try_inject))
    gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(2000, try_inject))

init_addon()
