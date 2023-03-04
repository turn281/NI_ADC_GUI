import collections
import datetime
import os
import sys
import threading
import time
from copy import deepcopy

import nidaqmx
import numpy as np
import pandas as pd
import pyqtgraph as pg
import PySide6
import qt_material
from nidaqmx.constants import AcquisitionType, Edge
from PySide6 import QtCore, QtWidgets


class Gui(QtWidgets.QWidget):

    WINDOW_TITLE = 'NI ADC Measurement Software'
    WINDOW_POSITION = (100, 100)
    WINDOW_SIZE = (800, 700)
    DEFAULT_SETTING = {
        'channel': '0,1,2',
        'device': 'dev1',
        'data_length': 10000,
        'sampling_rate': 1000,
        'read_samples': 100,
        'save_file_dir': os.getcwd(),
        'save_file_name': 'measured_data',
    }
    COLORS = (  # Default color set.
        '#06D6A0',
        '#EF476F',
        '#EE9B00',
        '#4CC9F0',
        '#073B4C',
        '#560BAD',
        '#C81D25',
        '#323031',
        '#118AB2',
        '#FEE440',
    )

    def __init__(self, parent=None):
        self.app = QtWidgets.QApplication(sys.argv)
        super().__init__(parent)
        # Set path to QT plugin.
        dir_name = os.path.dirname(PySide6.__file__)
        plugin_path = os.path.join(dir_name, 'plugins', 'platforms')
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
        # Set appearance of the GUI window.
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setGeometry(*self.WINDOW_POSITION, *self.WINDOW_SIZE)
        qt_material.apply_stylesheet(self, theme='dark_teal.xml')

        # Set initial widgets.
        self._init_ui()
        self.plots = dict()

        # Set variables.
        self.cfg = dict()

        # Set QTimer.
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._update_graph)

    def _init_ui(self):
        # Set ui preference.
        self.entry_height = 40

        # Create layouts.
        body = QtWidgets.QVBoxLayout(self)
        setting_area = QtWidgets.QGridLayout()
        body.addLayout(setting_area, 1)
        graph_area = QtWidgets.QVBoxLayout()
        body.addLayout(graph_area, 1)

        # Create setting area.
        self.device_label = QtWidgets.QLabel('Device name')
        self.device_entry = QtWidgets.QTextEdit(self.DEFAULT_SETTING['device'])
        self.device_entry.setFixedHeight(self.entry_height)
        setting_area.addWidget(self.device_label, 0, 0, 1, 1)
        setting_area.addWidget(self.device_entry, 0, 1, 1, 2)

        self.channel_label = QtWidgets.QLabel('Use channels')
        self.channel_entry = QtWidgets.QTextEdit(
            self.DEFAULT_SETTING['channel'])
        self.channel_entry.setFixedHeight(self.entry_height)
        setting_area.addWidget(self.channel_label, 1, 0, 1, 1)
        setting_area.addWidget(self.channel_entry, 1, 1, 1, 2)

        self.save_file_dir_label = QtWidgets.QLabel('Save directory')
        self.save_file_dir_entry = QtWidgets.QTextEdit(
            self.DEFAULT_SETTING['save_file_dir'])
        self.save_file_dir_entry.setFixedHeight(self.entry_height)
        self.save_file_dir_button = QtWidgets.QPushButton('Reference')
        self.save_file_dir_button.clicked.connect(lambda: self._file_dialog())
        setting_area.addWidget(self.save_file_dir_label, 2, 0, 1, 1)
        setting_area.addWidget(self.save_file_dir_entry, 2, 1, 1, 1)
        setting_area.addWidget(self.save_file_dir_button, 2, 2, 1, 1)

        self.save_file_name_label = QtWidgets.QLabel('Save file name')
        self.save_file_name_entry = QtWidgets.QTextEdit(
            self.DEFAULT_SETTING['save_file_name'])
        self.save_file_name_entry.setFixedHeight(self.entry_height)
        setting_area.addWidget(self.save_file_name_label, 3, 0, 1, 1)
        setting_area.addWidget(self.save_file_name_entry, 3, 1, 1, 2)

        self.sampling_rate_label = QtWidgets.QLabel('Sampling rate\n[Hz]')
        self.sampling_rate_label.setAlignment(
            QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self.sampling_rate_entry = QtWidgets.QTextEdit(
            str(self.DEFAULT_SETTING['sampling_rate']))
        self.sampling_rate_entry.setFixedHeight(self.entry_height)
        setting_area.addWidget(self.sampling_rate_label, 4, 0, 1, 1)
        setting_area.addWidget(self.sampling_rate_entry, 4, 1, 1, 2)

        self.read_samples_label = QtWidgets.QLabel('Read samples')
        self.read_samples_entry = QtWidgets.QTextEdit(
            str(self.DEFAULT_SETTING['read_samples']))
        self.read_samples_entry.setFixedHeight(self.entry_height)
        setting_area.addWidget(self.read_samples_label, 5, 0, 1, 1)
        setting_area.addWidget(self.read_samples_entry, 5, 1, 1, 2)

        self.measurement_button = QtWidgets.QPushButton('Start measurement')
        self.measurement_button.setCheckable(True)
        self.measurement_button.toggled.connect(
            lambda x: self._start_measurement(x))
        setting_area.addWidget(self.measurement_button, 6, 0, 1, 3)

        # Create graph area.
        self.time_history = pg.GraphicsLayoutWidget()
        self.plt = self.time_history.addPlot(
            axisItems={'bottom': pg.DateAxisItem()})
        self.plt.addLegend(offset=(10, 10))
        self.plt.showGrid(x=True, y=True)
        graph_area.addWidget(self.time_history)

    def _file_dialog(self):
        """File dialog to select save directory."""
        _dir = os.path.abspath(os.path.dirname(__file__))
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Save directory', _dir)
        self.save_file_dir_entry.setText(dir_path)

    def _set_config(self):
        self.cfg.update(self.DEFAULT_SETTING)
        # Update configs.
        self.cfg['channel'] = [
            int(i) for i in self.channel_entry.toPlainText().split(',')]
        self.cfg['device'] = self.device_entry.toPlainText()
        self.cfg['sampling_rate'] = int(self.sampling_rate_entry.toPlainText())
        self.cfg['read_samples'] = int(self.read_samples_entry.toPlainText())
        self.cfg['save_file_dir'] = self.save_file_dir_entry.toPlainText()
        self.cfg['save_file_name'] = self.save_file_name_entry.toPlainText()

    def _add_plot(self):
        for i, value_key in enumerate(self.cfg['channel']):
            self.plots[value_key] = self.plt.plot(
                pen=self.COLORS[i % 10],
                name=f'{value_key} ch',
            )

    def _remove_plot(self):
        for item in self.plots.values():
            self.plt.removeItem(item)

    def _reset_graph(self):
        self._remove_plot()
        self.graph_data = None

    def _start_measurement(self, checked):
        if checked:
            self._start()
            self.measurement_button.setText('Stop measurement')
        else:
            self._stop()
            self.measurement_button.setText('Start measurement')

    def _start(self):
        self._set_config()
        self._reset_graph()
        self._add_plot()
        self.measurement = DataAcquisition(self.cfg)
        self.measurement.start()
        self.timer.start()

    def _stop(self):
        self.measurement.exit()
        self.timer.stop()

    def _update_graph(self):
        if len(self.measurement.stored_data) != 0:
            data = self.measurement.stored_data.copy()
            self.measurement.stored_data = list()
            data = np.vstack(data)
            data[:, 0] *= 1e-9
            if self.graph_data is None:
                self.graph_data = data
            else:
                self.graph_data = np.vstack([self.graph_data, data])
            for i, value_key in enumerate(self.cfg['channel']):
                self.plots[value_key].setData(
                    self.graph_data[:, 0],
                    self.graph_data[:, i+1]
                )
        else:
            time.sleep(0.1)


class Measurement(threading.Thread):
    """Measurement thread class."""

    def __init__(self, cfg):
        """Initialization of measurement class.

        Args:
            cfg (dict): A dict of measurement settings.
        """
        super().__init__()

        self.channel = [int(_ch) for _ch in cfg['channel']]
        self.device = cfg['device']
        self.dataLength = int(cfg['data_length'])
        self.sampling_rate = int(cfg['sampling_rate'])
        self.read_samples = int(cfg['read_samples'])
        self.read_timeout = self.read_samples / self.sampling_rate

        self.q_init()
        self.lock = False
        self.exit_ = False
        self.daemon = True

    def q_init(self):
        """Initialize queues for measurement data and time."""
        self.data_queue = [collections.deque(
            maxlen=self.dataLength) for _ in range(len(self.channel)+1)]

    def run(self):
        """Measure and add data to queue."""
        self.task = nidaqmx.Task()
        _channel = str(self.channel[0]) if len(
            self.channel) == 1 else f'{min(self.channel)}:{max(self.channel)}'
        _channel_bool = [_ch in self.channel for _ch in range(
            min(self.channel), max(self.channel)+1)]
        self.task.ai_channels.add_ai_voltage_chan(
            f'{self.device}/ai{_channel}', min_val=-5, max_val=5)
        self.task.timing.cfg_samp_clk_timing(
            self.sampling_rate, u'', Edge.RISING, AcquisitionType.CONTINUOUS)
        self.task.start()
        data = [list()] * (len(self.channel)+1)

        while True:
            if self.exit_:
                break
            starttime = time.time_ns()
            _data = self.task.read(
                self.read_samples, timeout=self.read_timeout)
            _data = [_data] if len(self.channel) == 1 else _data
            _data = [d for i, d in enumerate(_data) if _channel_bool[i]]
            data = [lst + _lst for lst, _lst in zip(data, _data)]
            if not self.lock:
                self.data_queue[0].extend(
                    np.linspace(starttime, starttime +
                                self.read_timeout*1e+9, 1+len(data[0]))[:-1]
                )
                for _channel in range(len(self.channel)):
                    self.data_queue[_channel+1].extend(data[_channel])
                data = [list()] * (len(self.channel)+1)

    def exit(self):
        """Close measurement task."""
        self.exit_ = True
        self.task.stop()
        self.task.close()


class DataAcquisition(threading.Thread):
    """Data acquisition class."""

    def __init__(self, cfg):
        """Initialize socket server.

        Args:
            cfg (dict): Measurement settings.
        """
        super().__init__()
        self.cfg = cfg
        self.exit_ = False
        self.stored_data = list()

        self.columns = ['timestamp'] + [f'ch_{i}' for i in self.cfg['channel']]
        # Create save folder and file.
        self.save_folder = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=9), 'JST')
        ).strftime('%Y%m%d%H%M%S')
        self.save_folder_dir = \
            f'{self.cfg["save_file_dir"]}/{self.save_folder}'
        os.makedirs(self.save_folder_dir)
        # Export measurement setting.
        _cfg = [f'{k}: {v}\n' for k, v in self.cfg.items()]
        with open(f'{self.save_folder_dir}/setting.txt', 'w') as f:
            f.writelines(_cfg)
        pd.DataFrame([], columns=self.columns).to_csv(
            f'{self.save_folder_dir}/{self.cfg["save_file_name"]}.csv',
            mode='x',
            index=False,
        )

        self.daemon = True

    def _start_recording(self):
        """Start measurement thread."""
        # start to measurement
        self.measure = Measurement(self.cfg)
        self.measure.start()
        print('Recording is started.')

    def _data_acquisition(self):
        """Get data from measurement queue and output into pickle."""
        self.measure.lock = True
        data = deepcopy(self.measure.data_queue)
        self.measure.q_init()
        self.measure.lock = False
        if len(data[0]) > 0:
            self.result = np.array(data).T.reshape(
                (-1, len(self.cfg['channel'])+1))
            self._export_data()
            print('Exporting is finished successfully.')
            self.stored_data.append(self.result.copy())

    def _export_data(self):
        """Export measurement data to csv file."""
        pd.DataFrame(self.result, columns=self.columns).to_csv(
            f'{self.save_folder_dir}/{self.cfg["save_file_name"]}.csv',
            mode='a',
            index=False,
            header=False,
        )

    def exit(self):
        """Exit connection between container."""
        self.exit_ = True
        self.measure.exit()
        print('Measurement finished.')

    def run(self):
        """Start to receive socket communication."""
        self._start_recording()
        while True:
            if self.exit_:
                break
            else:
                time.sleep(1)
                self._data_acquisition()


if __name__ == '__main__':
    gui = Gui()
    gui.show()
    sys.exit(gui.app.exec())
