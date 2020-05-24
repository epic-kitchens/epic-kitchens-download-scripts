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
                 base_output=str(Path.home()),
                 splits_path_epic_55='data/epic_55_splits.csv',
                 splits_path_epic_100='data/epic_100_splits.csv'):
        self.base_url_55 = epic_55_base_url.rstrip('/')
        self.base_url_100 = epic_100_base_url.rstrip('/')
        self.base_output = os.path.join(base_output, 'EPIC-KITCHENS')
        self.videos_per_split = {}
        self.challenges_splits = []
        self.epic_55_video_list = []
        self.parse_splits(splits_path_epic_55, splits_path_epic_100)

    def download_file(self, url, output_path):
        Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)

        try:
            with urllib.request.urlopen(url) as response, open(output_path, 'wb') as output_file:
                print('Downloading from\n\t{}\nto\n\t{}'.format(url, output_path))
                shutil.copyfileobj(response, output_file)
        except urllib.error.HTTPError as e:
            print('Could not download file from {}\nError: {}'.format(url, str(e)))

    def parse_bool(self, b):
        return b.lower().strip() in ['true', 'yes', 'y']

    def parse_splits(self, epic_55_splits_path, epic_100_splits_path):
        epic_55_videos = {}

        with open(epic_55_splits_path) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',')

            for row in reader:
                epic_55_videos[row['video_id']] = row['split']

        with open(epic_100_splits_path) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',')
            self.challenges_splits = [f for f in reader.fieldnames if f != 'video_id']

            for f in self.challenges_splits:
                self.videos_per_split[f] = []

            for row in reader:
                video_id = row['video_id']
                parts = video_id.split('_')
                participant = int(parts[0].split('P')[1])
                extension = len(parts[1]) == 3
                epic_55_split = None if extension else epic_55_videos[video_id]
                v = {'video_id': video_id, 'participant': participant, 'extension': extension,
                     'epic_55_split': epic_55_split}

                for split in self.challenges_splits:
                    if self.parse_bool(row[split]):
                        self.videos_per_split[split].append(v)

    def download_consent_forms(self, video_dicts):
        files = ['ConsentForm.pdf', 'ParticipantsInformationSheet.pdf']

        for f in files:
            output_path = os.path.join(self.base_output, 'ConsentForms', f)
            url = '/'.join([self.base_url_55, 'ConsentForms', f])
            self.download_file(url, output_path)

    def download_videos(self, video_dicts):
        print('Download videos')

    def download_rgb_frames(self, video_dicts):
        print('Download rgb frames')

    def download_flow_frames(self, video_dicts):
        print('Download flow frames')

    def download_object_detection_images(self, video_dicts):
        print('Download object detection images')

    def download(self, what=('videos', 'rgb_frames', 'flow_frames', 'object_detection_images', 'consent_forms'),
                 participants='all', splits='all', challenges='all', extension_only=False, epic55_only=False):

        video_dicts = {}

        if splits == 'all' and challenges == 'all':
            download_splits = self.challenges_splits
        elif splits == 'all':
            download_splits = [cs for cs in self.challenges_splits for c in challenges if c == cs.split('_')[0]]
        elif challenges == 'all':
            download_splits = [cs for cs in self.challenges_splits for s in splits if s in cs.partition('_')[2]]
        else:
            download_splits = [cs for cs in self.challenges_splits for c in challenges for s in splits
                               if c == cs.split('_')[0] and s in cs.partition('_')[2]]

        for ds in download_splits:
            if participants == 'all' and not extension_only and not epic55_only:
                vl = self.videos_per_split[ds]
            else:
                # we know that only one between extension_only and epic_55_only will be True
                vl = [v for v in self.videos_per_split[ds] if (extension_only and v['extension']) or
                                                              (epic55_only and not v['extension'])]

                if participants != 'all':
                    vl = [v for v in vl if v['participant'] in participants]

            video_dicts.update({v['video_id']: v for v in vl})  # we use a dict to avoid duplicates

        if epic55_only:
            source = 'EPIC 55'
        elif extension_only:
            source = 'EPIC 100 (extension only)'
        else:
            source = 'EPIC 100'

        what_str = ', '.join(' '.join(w.split('_')) for w in what)
        participants_str = 'all' if participants == 'all' else ', '.join(['P{:02d}'.format(p) for p in participants])

        print('='*120)
        print('Going to download: {}\n'
              'for challenges: {}\n'
              'splits: {}\n'
              'participants: {}\n'
              'data source: {}'.format(what_str, challenges, splits, participants_str, source))
        print('='*120)

        for w in what:
            msg = '| Downloading {} now |'.format(' '.join(w.split('_')))
            print('-' * len(msg))
            print(msg)
            print('-' * len(msg))
            func = getattr(self, 'download_{}'.format(w))
            func(video_dicts)

        print('All done, bye!')
        print('=' * 120)


def parse_args():
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
    parser.add_argument('--extension_only', action='store_true', help='Download extension only')
    parser.add_argument('--epic55_only', action='store_true', help='Download only EPIC 55''s data')
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

    args = parser.parse_args()
    assert not (args.extension_only and args.epic55_only), 'You can specify either --extension_only or --epic55_only' \
                                                           ', but not both'
    return args


if __name__ == '__main__':
    # works with Python 3.5+  # TODO check python version and raise exception
    args = parse_args()

    what = ('videos', 'rgb_frames', 'flow_frames', 'object_detection_images', 'consent_forms') if args.what is None \
        else args.what
    challenges = 'all' if args.challenges is None else args.challenges
    splits = 'all' if args.splits is None else args.splits

    if args.participants != 'all':
        try:
            participants = [int(p.strip()) for p in args.participants.split(',')]
        except ValueError:
            print('Invalid participants arguments: {}.'
                  '\nYou can specif a single participant, e.g. `--participants 1` or\n'
                  'a comma-separated list of them, e.g. `--participants 1,2,3`.'
                  '\nUsing all participants now'.format(args.participants))
            participants = 'all'
    else:
        participants = 'all'

    downloader = EpicDownloader(base_output=args.output_path)
    downloader.download(what=what, participants=participants, splits=splits, challenges=challenges,
                        extension_only=args.extension_only, epic55_only=args.epic55_only)
