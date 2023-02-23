# NI_ADC_GUI
GUI for analog signal measurement with NI's (National Instruments) AD Converter.

## Requirements
* Python3 runtime environment
* NI-DAQmx (Windows OS only)
* packages
    * nidaqmx (https://pypi.org/project/nidaqmx/) etc.
    * Required packages can be installed with the following command:
    ```
    pip install -r requirements.txt
    ```

See https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z0000019Pf1SAE&l=ja-JP

## Run
1. Connect AD converter to PC via USB.

2. Run application with the following command:
```
python niadc_gui.py
```

3. Set measurement setting and start measurement.
    * The following settings are available.
    
    | Name | Discription |
    | :--: | :-- |
    | device name | Device number. (it can be confirmed using NI MAX) |
    | use channel | Channel number of analog input on ADC. |
    | save directory | The path to the directory where the measurement file is to be saved. |
    | save file name | The name of csv file. |
    | sampling rate [Hz] | Number of data read per second. |
    | read samples | Number of data to be read at one time. |
    | max queue size | Size of the measurement thread queue. (default values are fine in most cases) |

    * Press "START MEASUREMENT" button after modify measurement settings.
