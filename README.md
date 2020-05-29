# The EPIC Kitchens 100 downloader

We provide a `python` script to download the EPIC Kitchens 100 dataset, either in its entirety or in parts (e.g. only RGB frames). You can download data for a subset of participants, as well as a specific split for a certain challenge (e.g. the `test` split for `action retrieval`). You can also download only the dataset's extension, i.e. only the new data collected for EPIC Kitchens 100.

#### Python version

The script requires Python **3.5+** and  **no external libraries**.

# Using the script

The script accepts a number of arguments that allow you to specify what you want to download: by default the script will download **everything** to your **home directory**. 


## Download only certain data types

We provide videos, RGB/optical flow frames, GoPro's metadata (for the extension only) and object detection frames (for EPIC Kitchens 55's videos only). You can also download the consent form templates.

If you want to download only one (or a subset) of the above, you can do so with the following self-explanatory arguments:

- `--videos`
- `--rgb-frames`
- `--flow-frames`
- `--object-detection-images`
- `--metadata`
- `--consent-forms`

If you want to download only videos, then:

```bash
python epic_downloader.py --videos
```

Note that these arguments can be **combined** to download multiple things. For example:

```bash
python epic_downloader.py --rgb-frames --flow-frames
```

Will download both RGB and optical flow frames.

## Specifying participants

You can use the argument `--participants` if you want to download data for only a subset of the participants. Participants must be specified with their *numerical* ID. 

You can specify a single participant, e.g. `--participants 1` for P01 or a comma-separated list of them, e.g. `--participants 1,2,3` for participants `P01`, `P02` and `P03`

This argument can also be combined with the aforementioned arguments. For example:

```bash
python epic_downloader.py --videos --participants 1,2,3
```

Will download only videos from `P01, P02` and `P03`.

## Specifying a challenge split

You can choose to download data for a specific **split** of one of the three **challenges**: action recognition, domain adaptation and action retrieval. 

To specify a **challenge**, use the following arguments:

- `--action-recognition`
- `--domain-adaptation`
- `--action-retrieval`

To specify a **split**, use one (or more) of the following arguments.

| argument               | challenge(s) available                   |
|------------------------|------------------------------------------|
| `--train`              | action recognition, action retrieval     |
| `--val`                | action recognition only                  |
| `--test`               | action recognition, action retrieval     |
| `--source-train`       | domain adaptation                        |
| `--source-test`        | domain adaptation                        |
| `--target-train`       | domain adaptation                        |
| `--target-test`        | domain adaptation                        |
| `--val-source-train`   | domain adaptation                        |
| `--val-source-test`    | domain adaptation                        |
| `--val-target-train`   | domain adaptation                        |
| `--val-target-test`    | domain adaptation                        |

Combine challenge and split arguments to download the relevant splits. For example:

```bash
python epic_downloader.py --action-recognition --train
```

Will download all data for the training set split for action recognition. 

```bash
python epic_downloader.py --action-retrieval --test --domain-adaptation --target-test 
```

Will download all data for the test set split for action retrieval, as well as all data for the target test split for domain adaptation. 

Again, these arguments can be combined with all others. For example

```bash
python epic_downloader.py --flow-frames --participants 7 --action-recognition --test
```

Will download only optical flow frames for `P07`'s videos contained in the test split for action recognition. 

Arguments can be passed in any order.

You can also specify only split arguments without a challenge. For example

```bash
python epic_downloader.py --test --videos
```

Will download all videos in the test sets of the action recognition and action retrieval challenges. 

```bash
python epic_downloader.py --train --val
```

Will download all data for the training sets of action recognition and action retrieval, as well as the validation set for action recognition.

Refer to the table above to check what gets downloaded with each split argument.

#### Note on domain adaptation's validation sets

These refer to unique splits which should be used only to validate hyper-parameters. For example, `-- val-target-test` will download the target test set used for validation. See the EPIC-Kitchens-100 annotations repo [here](https://github.com/epic-kitchens/EPIC-Kitchens-100-Annotations) for more information about domain adaptation splits.

## Download extension or EPIC Kitchens 55 only

You can do so with the `--extension-only` and `--epic55-only` arguments. For example:

```bash
python epic_downloader.py --videos --extension-only
```

Will download only the newly collected videos, while 

```bash
python epic_downloader.py --participants 3 --epic55-only
```

Will download all data from `P03` collected for EPIC Kitchens 55.

## Output

By default data will be downloaded to your home directory. You can change the output folder with the `--output-path` argument. 

Data will be stored in a subdirectory named `EPIC-KITCHENS`. 

### Folders structure

Data will be split amongst participants under the output directory:

<pre><font color="#0087FF">/home/username/EPIC-KITCHENS/</font>
├── <font color="#0087FF">ConsentForms</font>
└── <font color="#0087FF">P01</font>
    ├── <font color="#0087FF">flow_frames</font>
    ├── <font color="#0087FF">meta_data</font>
    ├── <font color="#0087FF">object_detection_images</font>
    ├── <font color="#0087FF">rgb_frames</font>
    └── <font color="#0087FF">videos</font>
</pre>

Each leaf directory will contain `.tar` or `.mp4` files accordingly.
