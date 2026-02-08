from kivy.app import App
from kivy.lang import Builder

KV = '''
BoxLayout:
    orientation: 'vertical'
    padding: 20
    spacing: 10

    Label:
        id: lbl
        text: 'Olá, Eddie Mobile!'
        font_size: '24sp'

    Button:
        text: 'Clique-me'
        size_hint_y: None
        height: '48dp'
        on_release: app.on_button()
'''

class MobileApp(App):
    def build(self):
        return Builder.load_string(KV)

    def on_button(self):
        self.root.ids.lbl.text = 'Você clicou!'

if __name__ == '__main__':
    MobileApp().run()
