from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from MonitorMainWindow import MonitorMainWindow

app = QApplication(sys.argv)
icon = QIcon("MonitorQtApp/images/hammer.ico")
app.setWindowIcon(icon)
mainform = MonitorMainWindow()

mainform.show()
sys.exit(app.exec_())


