import argparse
import os
import csv
import shutil
import urllib.request
import urllib.error
from pathlib import Path


class EpicDownloader:
    def __init__(self,
                 epic_55_base_url='https://data.bris.ac.uk/datasets/3h91syskeag572hl6tvuovwv4d',
                 epic_100_base_url='https://data.bris.ac.uk/datasets/2g1n6qdydwa9u22shpxqzp0t8m',
                 base_output=str(Path.home())):
        self.base_url_55 = epic_55_base_url.rstrip('/')
        self.base_url_100 = epic_100_base_url.rstrip('/')
        self.base_output = os.path.join(base_output, 'EPIC-KITCHENS')
        self.videos_per_split = {}
        self.challenges_splits = []
        self.parse_splits('data/splits.csv')

    def download_file(self, url, output_path):
        Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)

        try:
            with urllib.request.urlopen(url) as response, open(output_path, 'wb') as output_file:
                print('Downloading {} to {}'.format(url, output_path))
                shutil.copyfileobj(response, output_file)
        except urllib.error.HTTPError as e:
            print('Could not download file from {}\nError: {}'.format(url, str(e)))

    def parse_bool(self, b):
        return b.lower().strip() in ['true', 'yes', 'y']

    def parse_splits(self, list_path):
        with open(list_path) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',')
            self.challenges_splits = [f for f in reader.fieldnames if f != 'video_id']

            for f in self.challenges_splits:
                self.videos_per_split[f] = []

            for row in reader:
                video_id = row['video_id']
                parts = video_id.split('_')
                participant = parts[0]
                extension = len(parts[1]) == 3
                v = {'video_id': video_id, 'participant': participant, 'extension': extension}

                for split in self.challenges_splits:
                    if self.parse_bool(row[split]):
                        self.videos_per_split[split].append(v)

    def download_consent_forms(self, **kwargs):
        files = ['ConsentForm.pdf', 'ParticipantsInformationSheet.pdf']

        for f in files:
            output_path = os.path.join(self.base_output, 'ConsentForms', f)
            url = '/'.join([self.base_url_55, 'ConsentForms', f])
            self.download_file(url, output_path)

    def download_videos(self, **kwargs):
        print('Download videos', kwargs)

    def download_rgb_frames(self, **kwargs):
        print('Download rgb frames', kwargs)

    def download_flow_frames(self, **kwargs):
        print('Download flow frames', kwargs)

    def download_object_detection_images(self, **kwargs):
        print('Download object detection imagesPytho', kwargs)

    def download(self, what=('videos', 'rgb_frames', 'flow_frames', 'object_detection_images', 'consent_forms'),
                 participants='all', splits=('train', 'val', 'test'), challenges=('ar', 'da', 'cmr'),
                 extension_only=False, epic55_only=False):

        download_list = []

        for c in challenges:
            for s in splits:
                field = '{}_{}'.format(c, s)
                # TODO fix this, as we won't have val split for cmr for example
                # assert field in self.splits, 'Invalid combination of challenge-split: {}-{}'.format(c, s)

                if participants == 'all' and not extension_only and not epic55_only:
                    download_list.extend(self.videos_per_split[field])
                else:
                    pass  # TODO: filter video lists based on participants and epic version

        # TODO make sure the final list doesn't contain duplicates, which is possible if we select all (there are
        # overlaps between splits

        for w in what:
            func = getattr(self, 'download_{}'.format(w))
            func(participants=participants, splits=splits)


if __name__ == '__main__':
    # works with Python 3.5+  # TODO check python version and raise exception

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('--output_path', nargs='?', type=str, default=Path.home(),
                        help='Path where to download files. Default is {}'.format(Path.home()))
    parser.add_argument('--videos', dest='what', action='append_const', const='videos', help='Download videos')
    parser.add_argument('--rgb_frames', dest='what', action='append_const', const='rgb_frames',
                        help='Download rgb frames')
    parser.add_argument('--flow_frames', dest='what', action='append_const', const='flow_frames',
                        help='Download optical flow frames')
    parser.add_argument('--object_detection_images', dest='what', action='append_const',
                        const='object_detection_images', help='Download object detection images (only for EPIC 55)')
    parser.add_argument('--consent_forms', dest='what', action='append_const', const='consent_forms',
                        help='Download consent_forms')
    parser.add_argument('--participants', nargs='?', type=str, default='all',
                        help='Specify participants IDs. You can specif a single participant, e.g. `--participants 1` or'
                             'a comma-separated list of them, e.g. `--participants 1,2,3`')
    parser.add_argument('--extension_only', nargs='?', type=bool, default=False, help='Download extension only')
    parser.add_argument('--epic55_only', nargs='?', type=bool, default=False, help='Download only EPIC 55''s data')
    parser.add_argument('--action_recognition', dest='challenges', action='append_const', const='ar',
                        help='Download data for the action recognition challenge')
    parser.add_argument('--domain_adaptation', dest='challenges', action='append_const', const='da',
                        help='Download data for the domain adaptation challenge')
    parser.add_argument('--cross_modal_retrieval', dest='challenges', action='append_const', const='cmr',
                        help='Download data for the cross modal retrieval challenge')
    parser.add_argument('--train', dest='splits', action='append_const', const='train',
                        help='Download data from the training split (for action recognition and cross modal retrieval)')
    parser.add_argument('--val', dest='splits', action='append_const', const='val',
                        help='Download data from the validation split (for action recognition only)')
    parser.add_argument('--test', dest='splits', action='append_const', const='test',
                        help='Download data from the testing split (for action recognition and cross modal retrieval)')
    parser.add_argument('--source_train', dest='splits', action='append_const', const='source_train',
                        help='Download data from the source training split for domain adaptation')
    parser.add_argument('--source_test', dest='splits', action='append_const', const='source_test',
                        help='Download data from the source testing split for domain adaptation')
    parser.add_argument('--target_train', dest='splits', action='append_const', const='target_train',
                        help='Download data from the target training split for domain adaptation')
    parser.add_argument('--target_test', dest='splits', action='append_const', const='target_test',
                        help='Download data from the target testing split for domain adaptation')
    parser.add_argument('--val_source_train', dest='splits', action='append_const', const='val_source_train',
                        help='Download the smaller source train set used to validate hyper-parameters for domain '
                             'adaptation')
    parser.add_argument('--val_source_test', dest='splits', action='append_const', const='val_source_test',
                        help='Download the smaller source test set used to validate hyper-parameters for domain '
                             'adaptation')
    parser.add_argument('--val_target_train', dest='splits', action='append_const', const='val_target_train',
                        help='Download the smaller target train set used to validate hyper-parameters for domain '
                             'adaptation')
    parser.add_argument('--val_target_test', dest='splits', action='append_const', const='val_target_test',
                        help='Download the smaller target test set used to validate hyper-parameters for domain '
                             'adaptation')

    # TODO: check for incompatible arguments
    # TODO: parse participants

    args = parser.parse_args()

    what = ('videos', 'rgb_frames', 'flow_frames', 'object_detection_images', 'consent_forms') if args.what is None \
        else args.what
    challenges = ('ar', 'da', 'cmr') if args.challenges is None else args.challenges
    splits = ('train', 'val', 'test') if args.splits is None else args.splits

    downloader = EpicDownloader(base_output=args.output_path)
    downloader.download(what=what, participants=args.participants, splits=splits, challenges=challenges,
                        extension_only=args.extension_only, epic55_only=args.epic55_only)
