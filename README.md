# The EPIC KITCHENS downloader

We provide a `python` script to download both the EPIC KITCHENS-100 and EPIC KITCHENS-55 datasets, either in its entirety or in parts (e.g. only RGB frames). You can download data for a subset of participants, as well as a specific split for a certain challenge (e.g. the `test` split for `action retrieval`). You can also download only the dataset's extension, i.e. only the new data collected for EPIC KITCHENS-100.

#### Python version

The script requires Python **3.5+** and  **no external libraries**.

## `Error 404 / Errno 104 Connection reset by peer` when using the script

We are aware of an issue occurring when using the download script depending on the region, e.g.

```bash
Could not download file from https://data.bris.ac.uk/datasets/3h91syskeag572hl6tvuovwv4d/frames_rgb_flow/rgb/train/P01/P01_01.tar
Error: [Errno 104] Connection reset by peer
```

While we fix this problem, please use Academic Torrents if you face this issue. You can find [EPIC-KITCHENS-55 here](https://academictorrents.com/details/d08f4591d1865bbe3436d1eb25ed55aae8b8f043) and [EPIC-KITCHENS-100 here](https://academictorrents.com/details/c92b4a3cd3834e9af9666ac82379ff15ca289a83).

# Errata

**Important:** We have recently detected an error in our pre-extracted RGB and Optical flow frames for two videos in our dataset. This does not affect the videos themselves or any of the annotations in this github. 

However, if you've been using our pre-extracted frames or object/hand detections and masks, you can use the script to download the correct files:

```bash
python epic_downloader.py --errata
```

This will download only the affected files:

- `P01/rgb_frames/P01_109.tar`
- `P01/flow_frames/P01_109.tar`
- `P01/hand-objects/P01_109.pkl`
- `P01/masks/P01_109.pkl`
- `P27/rgb_frames/P27_103.tar`
- `P27/flow_frames/P27_103.tar`
- `P27/hand-objects/P27_103.pkl`
- `P27/masks/P27_103.pkl`

If you had downloaded these files previously, they will be overwritten.

As of 26/09/2020, regardless of the `--errata` argument, the script will **always** download the correct version of the
above files.

As of 02/12/2020, the correct object/hand detections and masks will also be downloaded regardless of the `--errata` argument.

# Using the script

The script accepts a number of arguments that allow you to specify what you want to download: by default the script will download **everything** to your **home directory**. 


## Download only certain data types

We provide videos, RGB/optical flow frames, GoPro's metadata (for the extension only) and object detection frames (for EPIC KITCHENS-55's videos only). You can also download the consent form templates.

If you want to download only one (or a subset) of the above, you can do so with the following self-explanatory arguments:

- `--videos`
- `--rgb-frames`
- `--flow-frames`
- `--object-detection-images`
- `--masks`
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

For more information about objects masks (which you download with `--masks`), check out [the dedicated repository](https://github.com/epic-kitchens/epic-kitchens-100-object-masks).

## Specifying participants

You can use the argument `--participants` if you want to download data for only a subset of the participants. Participants can be specified with their numerical *or* string ID. 

You can specify a single participant, e.g. `--participants 1` or `--participants P01` for participant `P01`, or a comma-separated list of them, e.g. `--participants 1,2,3` or `--participants P01,P02,P03` for participants `P01`, `P02` and `P03`

This argument can also be combined with the aforementioned arguments. For example:

```bash
python epic_downloader.py --videos --participants 1,2,3
```

Will download only videos from `P01, P02` and `P03`.

## Specifying specific videos

You can use the argument `--specific-videos` if you want to download a specific subset of videos, without having to download all videos from certain participants. Videos must be specified with their string ID.

You can specifiy a single video e.g. `--specific-videos P01_01` for video `P01_01`, or a comma-seperated list of them, e.g. `--specific-videos P01_01,P02_122,P03_04` for videos `P01_01`, `P02_122` and `P03_04`.

This argument can also be combined with the aforementioned arguments. For example:

```bash
python epic_downloader.py --videos --participants P01 --specific-videos P02_122,P03_04 
```

Will download all the videos from participant `P01`, but only videos `P02_122` and `P03_04` from participants `P02` and `P03`. 

**Note:** if the same participant is specified in the partipant and specific-videos argument, the specific video of that participant will not be exclusively downloaded. Instead, all videos from that particpant will be downloaded e.g. `--particpants P01 --specific-videos P01_01` will download all videos from participant P01, rather than just P01_01.

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

These refer to unique splits which should be used only to validate hyper-parameters. For example, `-- val-target-test` will download the target test set used for validation. See the EPIC-KITCHENS-100 annotations repo [here](https://github.com/epic-kitchens/EPIC-Kitchens-100-Annotations) for more information about domain adaptation splits.

## Download extension or EPIC KITCHENS-55 only

You can do so with the `--extension-only` and `--epic55-only` arguments. For example:

```bash
python epic_downloader.py --videos --extension-only
```

Will download only the newly collected videos, while 

```bash
python epic_downloader.py --participants 3 --epic55-only
```

Will download all data from `P03` collected for EPIC KITCHENS-55.

## Output

By default data will be downloaded to your home directory. You can change the output folder with the `--output-path` argument. 

Data will be stored in a subdirectory named `EPIC-KITCHENS`. 

### Folders structure

Data will be split amongst participants under the output directory:

<pre><font color="#0087FF">/home/username/EPIC-KITCHENS/</font>
├── <font color="#0087FF">ConsentForms</font>
└── <font color="#0087FF">P01</font>
    ├── <font color="#0087FF">flow_frames</font>
    ├── <font color="#0087FF">hand-objects</font>
    ├── <font color="#0087FF">masks</font>
    ├── <font color="#0087FF">meta_data</font>
    ├── <font color="#0087FF">rgb_frames</font>
    └── <font color="#0087FF">videos</font>
</pre>

Each leaf directory will contain `.tar`, `.mp4` or `.pkl` files accordingly. 

Previously fully downloaded files will be skipped, so you can download large batches of files over multiple runs.

Errata files will be overwritten. Once you download the correct version of these files, they will be safely skipped in 
following runs.

## Download speed

Download speed might be (very) slow depending on the region. 

In such case we recommend using Academic Torrents instead of this script. You can find [EPIC-KITCHENS-55 here](https://academictorrents.com/details/d08f4591d1865bbe3436d1eb25ed55aae8b8f043) and [EPIC-KITCHENS-100 here](https://academictorrents.com/details/cc2d9afabcbbe33686d2ecd9844b534e3a899f4b).
