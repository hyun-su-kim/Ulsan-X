import sys

import rclpy
from PyQt5.QtWidgets import QApplication

from ulsan_gui.ros_node import RosNode, RosSpinThread
from ulsan_gui.main_window import MainWindow


def main():
    rclpy.init()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    node = RosNode()
    spin_thread = RosSpinThread(node)
    spin_thread.start()

    window = MainWindow(node)
    window.show()

    exit_code = app.exec_()

    spin_thread.stop()
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
