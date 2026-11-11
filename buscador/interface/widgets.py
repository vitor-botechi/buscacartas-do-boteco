"""Peças pequenas da interface: textos de status, dica do mouse e atalhos de edição."""

import tkinter as tk


STATUS_TEXT = {
    "found": "✅ Encontrada",
    "soldout": "🟡 Cadastrada, mas indisponível",
    "none": "❌ Não encontrada",
    "blocked": "⚠ Site bloqueou a leitura — dê duplo clique para abrir",
    "unknown": "⚠ Não consegui ler — dê duplo clique para abrir",
    "error": "⚠ Falha de conexão — dê duplo clique para abrir",
}


class Tooltip:
    """Dica que aparece ao passar o mouse sobre um widget."""

    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1,
                 padx=6, pady=3).pack()

    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def enable_word_editing(entry):
    """Ctrl+Backspace e Ctrl+Delete apagam uma palavra; Ctrl+A seleciona tudo (o Tk não faz isso sozinho)."""

    def back(event):
        w = event.widget
        if w.selection_present():
            w.delete("sel.first", "sel.last")
            return "break"
        pos, text = w.index("insert"), w.get()
        i = pos
        while i > 0 and text[i - 1].isspace():
            i -= 1
        while i > 0 and not text[i - 1].isspace():
            i -= 1
        w.delete(i, pos)
        return "break"

    def forward(event):
        w = event.widget
        if w.selection_present():
            w.delete("sel.first", "sel.last")
            return "break"
        pos, text = w.index("insert"), w.get()
        i, n = pos, len(text)
        while i < n and not text[i].isspace():
            i += 1
        while i < n and text[i].isspace():
            i += 1
        w.delete(pos, i)
        return "break"

    def select_all(event):
        event.widget.selection_range(0, "end")
        event.widget.icursor("end")
        return "break"

    entry.bind("<Control-BackSpace>", back)
    entry.bind("<Control-Delete>", forward)
    entry.bind("<Control-a>", select_all)
    entry.bind("<Control-A>", select_all)
