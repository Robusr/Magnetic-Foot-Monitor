echo off

copy .\MonitorQtApp\mainwindow.ui MonitorAppMainWindow.ui
pyuic5 -o ui_MonitorAppMainWindow.py MonitorAppMainWindow.ui

pyrcc5 .\MonitorQtApp\res.qrc -o res_rc.py