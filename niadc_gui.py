import collections
import datetime
import numpy as np
import pandas as pd
import os
import sys
import threading
import time
from copy import copy, deepcopy

import tkinter as tk
from tkinter import messagebox as tkm
from tkinter import filedialog

import nidaqmx
from nidaqmx.constants import AcquisitionType, Edge


class Measurement(threading.Thread):
    """Measurement class."""

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
        self.setDaemon(True)

    def q_init(self):
        """Initialize queues for measurement data and time."""
        self.data_queue = [collections.deque(maxlen=self.dataLength) for _ in range(len(self.channel)+1)]

    def run(self):
        """Measure and add data to queue."""
        self.task = nidaqmx.Task()
        _channel = str(self.channel[0]) if len(self.channel) == 1 else f'{min(self.channel)}:{max(self.channel)}'
        _channel_bool = [_ch in self.channel for _ch in range(min(self.channel), max(self.channel)+1)]
        self.task.ai_channels.add_ai_voltage_chan(f'{self.device}/ai{_channel}', min_val=-5, max_val=5)
        self.task.timing.cfg_samp_clk_timing(self.sampling_rate, u'', Edge.RISING, AcquisitionType.CONTINUOUS)
        self.task.start()
        data = [list()] * (len(self.channel)+1)

        while True:
            starttime = time.time_ns()
            _data = self.task.read(self.read_samples, timeout=self.read_timeout)
            _data = [_data] if len(self.channel) == 1 else _data
            _data = [d for i, d in enumerate(_data) if _channel_bool[i]]
            data = [lst + _lst for lst, _lst in zip(data, _data)]
            if not self.lock:
                self.data_queue[0].extend(
                    np.linspace(starttime, starttime+self.read_timeout*1e+9, 1+len(data[0]))[:-1]
                )
                for _channel in range(len(self.channel)):
                    self.data_queue[_channel+1].extend(data[_channel])
                data = [list()] * (len(self.channel)+1)

    def exit(self):
        """Close task."""
        self.task.stop()
        self.task.close()


class GUI(tk.Frame):
    """GUI application for measurement."""

    WINDOW_TITLE = 'NIADC - DAQmx'
    WIDTH, HEIGHT = (600, 380)
    DEFAULT_SETTING = {
        'device': 'dev0',
        'channel': '0,1',
        'data_length': 10000,
        'sampling_rate': 1000,
        'read_samples': 100,
        'save_file_dir': 'C:/Users/user_name/Desktop/',
        'save_file_name': 'measured_data.csv',
    }

    def __init__(self, master=None):
        """Constructor of GUI class."""
        super().__init__(master)

        self.start = False
        self.set_cfg = False

        self.master.title(self.WINDOW_TITLE)
        self.master.geometry(f'{self.WIDTH}x{self.HEIGHT}')

        self._init_UI()
        self.settings_entries = {
            'channel': self.channel_entry,
            'device': self.device_entry,
            'data_length': self.data_length_entry,
            'sampling_rate': self.sampling_rate_entry,
            'read_samples': self.read_samples_entry,
            'save_file_dir': self.save_file_dir_entry,
            'save_file_name': self.save_file_name_entry,
        }

    def _init_UI(self):
        """Create labels, entries and buttoms."""
        self.device_label = tk.Label(self.master, text='device name')
        self.device_label.grid(row=0, column=0, columnspan=1, padx=5, pady=5)
        self.device_entry = tk.Entry(self.master, width=30)
        self.device_entry.insert(tk.END, self.DEFAULT_SETTING['device'])
        self.device_entry.grid(row=0, column=1, columnspan=1, padx=5, pady=5)

        self.channel_label = tk.Label(self.master, text='use channel')
        self.channel_label.grid(row=1, column=0, columnspan=1, padx=5, pady=5)
        self.channel_entry = tk.Entry(self.master, width=30)
        self.channel_entry.insert(tk.END, self.DEFAULT_SETTING['channel'])
        self.channel_entry.grid(row=1, column=1, columnspan=1, padx=5, pady=5)

        self.save_file_dir_label = tk.Label(self.master, text='save directory')
        self.save_file_dir_label.grid(row=2, column=0, columnspan=1, padx=5, pady=5)
        self.save_file_dir_entry = tk.Entry(self.master, width=30)
        self.save_file_dir_entry.insert(tk.END, self.DEFAULT_SETTING['save_file_dir'])
        self.save_file_dir_entry.grid(row=2, column=1, columnspan=1, padx=5, pady=5)
        self.save_file_dir_button = tk.Button(text='参照', width=10, command=self._dirdialog)
        self.save_file_dir_button.grid(row=2, column=2, columnspan=1, padx=5, pady=5)

        self.save_file_name_label = tk.Label(self.master, text='save file name')
        self.save_file_name_label.grid(row=3, column=0, columnspan=1, padx=5, pady=5)
        self.save_file_name_entry = tk.Entry(self.master, width=30)
        self.save_file_name_entry.insert(tk.END, self.DEFAULT_SETTING['save_file_name'])
        self.save_file_name_entry.grid(row=3, column=1, columnspan=1, padx=5, pady=5)

        self.sampling_rate_label = tk.Label(self.master, text='sampling rate [Hz]')
        self.sampling_rate_label.grid(row=4, column=0, columnspan=1, padx=5, pady=5)
        self.sampling_rate_entry = tk.Entry(self.master, width=30)
        self.sampling_rate_entry.insert(tk.END, self.DEFAULT_SETTING['sampling_rate'])
        self.sampling_rate_entry.grid(row=4, column=1, columnspan=1, padx=5, pady=5)

        self.read_samples_label = tk.Label(self.master, text='read samples')
        self.read_samples_label.grid(row=5, column=0, columnspan=1, padx=5, pady=5)
        self.read_samples_entry = tk.Entry(self.master, width=30)
        self.read_samples_entry.insert(tk.END, self.DEFAULT_SETTING['read_samples'])
        self.read_samples_entry.grid(row=5, column=1, columnspan=1, padx=5, pady=5)

        self.data_length_label = tk.Label(self.master, text='max queue size')
        self.data_length_label.grid(row=6, column=0, columnspan=1, padx=5, pady=5)
        self.data_length_entry = tk.Entry(self.master, width=30)
        self.data_length_entry.insert(tk.END, self.DEFAULT_SETTING['data_length'])
        self.data_length_entry.grid(row=6, column=1, columnspan=1, padx=5, pady=5)

        self.update_setting = tk.Button(text='update setting', width=10, command=self._update_setting)
        self.update_setting.grid(row=7, column=0, columnspan=1, padx=5, pady=5)

        self.status_label = tk.Label(self.master, text='Please enter and update settings')
        self.status_label.grid(row=7, column=1, columnspan=1, padx=5, pady=5)

        self.start_button = tk.Button(text='start', width=30, command=self._start)
        self.start_button.grid(row=8, column=1, columnspan=1, padx=5, pady=5)

        self.stop_button = tk.Button(text='stop', width=30, command=self._stop)
        self.stop_button.grid(row=9, column=1, columnspan=1, padx=5, pady=5)

    def _update_setting(self):
        self.cfg = {k: v.get() for k, v in self.settings_entries.items()}
        self.cfg['channel'] = [int(i) for i in self.cfg['channel'].split(',')]
        if '' in self.cfg.values():
            tkm.showinfo('Error', '全ての設定を入力してください')
        else:
            self.set_cfg = True
            self.status_label['text'] = 'Ready for measurement'
            self.model = DataAcquisition(self.cfg)

    def _start(self):
        if self.set_cfg:
            self.start = True
            self.status_label['text'] = 'Measuring...'
            self.start_measurement()
        else:
            tkm.showinfo('Error', '全ての設定を入力して更新してください')

    def _stop(self):
        if self.start:
            self.confirmation = tkm.askyesno('確認', '終了して良いですか？')
            if self.confirmation:
                self.start = False
                self.exit()

    def _dirdialog(self):
        _dir = os.path.abspath(os.path.dirname(__file__))
        _dir_path = filedialog.askdirectory(initialdir = _dir)
        self.save_file_dir_entry.delete(0,tk.END)
        self.save_file_dir_entry.insert(tk.END, str(_dir_path))

    def exit(self):
        self.master.destroy()
        self.model.exit()

    def start_measurement(self):
        self.model.start()


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

        self.columns = ['timestamp'] + [f'ch_{i}' for i in self.cfg['channel']]
        # Create save folder and file.
        self.save_folder = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9), 'JST')).strftime('%Y%m%d%H%M%S')
        self.save_folder_dir = f'{self.cfg["save_file_dir"]}/{self.save_folder}'
        os.makedirs(self.save_folder_dir)
        # Export measurement setting.
        _cfg = [f'{k}: {v}\n' for k, v in self.cfg.items()]
        with open(f'{self.save_folder_dir}/setting.txt', 'w') as f:
            f.writelines(_cfg)
        pd.DataFrame([], columns=self.columns).to_csv(
            f'{self.save_folder_dir}/{self.cfg["save_file_name"]}',
            mode='x',
            index=False,
        )

        self.setDaemon(True)

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
            self.result = np.array(data).T.reshape((-1, len(self.cfg['channel'])+1))
            self._export_data()
            print('Exporting is finished successfully.')

    def _export_data(self):
        """Export measurement data to csv file."""
        pd.DataFrame(self.result, columns=self.columns).to_csv(
            f'{self.save_folder_dir}/{self.cfg["save_file_name"]}',
            mode='a',
            index=False,
            header=False,
        )

    def exit(self):
        """Exit connection between container."""
        self.measure.exit()
        print('Measurement finished.')
        sys.exit(0)

    def run(self):
        """Start to receive socket communication."""
        self._start_recording()
        while True:
            if self.exit_:
                self.exit()
            else:
                time.sleep(1)
                self._data_acquisition()


if __name__ == '__main__':
    root = tk.Tk()
    window = GUI(master=root)
    window.mainloop()
