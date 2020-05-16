import argparse
import os
import csv
import shutil
import urllib.request
import urllib.error
from pathlib import Path


def download_file(url, output_path):
    Path(os.path.dirname(output_path)).mkdir(parents=True, exist_ok=True)

    try:
        with urllib.request.urlopen(url) as response, open(output_path, 'wb') as output_file:
            print('Downloading {} to {}'.format(url, output_path))
            shutil.copyfileobj(response, output_file)
    except urllib.error.HTTPError as e:
        print('Could not download file from {}\nError: {}'.format(url, str(e)))


class Epic55Downloader:
    def __init__(self, base_url='https://data.bris.ac.uk/datasets/3h91syskeag572hl6tvuovwv4d',
                 base_output=str(Path.home())):
        self.base_url = base_url.rstrip('/')
        self.base_output = os.path.join(base_output, 'EPIC-KITCHENS')
        self.participants = ['P{:02d}'.format(p) for p in range(1, 33)]
        self.videos = {p: [] for p in self.participants}
        self.read_video_list('epic_55_videos.csv', self.videos)

    def read_video_list(self, list_path, video_dict):
        with open(list_path) as csvfile:
            reader = csv.reader(csvfile, delimiter=',')

            for row in reader:
                video = row[0]
                participant = video.split('_')[0]
                video_dict[participant].append(video)

    def download_consent_forms(self, **kwargs):
        files = ['ConsentForm.pdf', 'ParticipantsInformationSheet.pdf']

        for f in files:
            output_path = os.path.join(self.base_output, 'ConsentForms', f)
            url = '/'.join([self.base_url, 'ConsentForms', f])
            download_file(url, output_path)

    def download_videos(self, **kwargs):
        print('Download videos', kwargs)

    def download_rgb_frames(self, **kwargs):
        print('Download rgb frames', kwargs)

    def download_flow_frames(self, **kwargs):
        print('Download flow frames', kwargs)

    def download_object_detection_images(self, **kwargs):
        print('Download object detection imagesPytho', kwargs)

    def download(self, what=('videos', 'rgb_frames', 'flow_frames', 'object_detection_images', 'consent_forms'),
                 participants='all', splits=('train', 'test')):

        for w in what:
            func = getattr(self, 'download_{}'.format(w))
            func(participants=participants, splits=splits)


class Epic100Downloader(Epic55Downloader):
    def __init__(self, base_url='https://data.bris.ac.uk/datasets/2g1n6qdydwa9u22shpxqzp0t8m',
                 base_output=str(Path.home())):
        super(Epic100Downloader, self).__init__(base_url=base_url, base_output=base_output)
        self.extension_only = False
        self.ext_participants = ['P{:02d}'.format(p) for p in
                                 [1, 2, 3, 4, 6, 7, 9, 11, 12, 22, 23, 25, 26, 27, 28, 30, 33, 34, 35, 36, 37]]
        self.new_participants = ['P{:02d}'.format(p) for p in [33, 34, 35, 36, 37]]
        self.participants.extend(self.new_participants)
        self.ext_videos = {p: [] for p in self.ext_participants}
        self.read_video_list('ext_videos.csv', self.ext_videos)
        self.videos.update(self.ext_videos)


if __name__ == '__main__':
    # works with Python 3.5+

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('--version', nargs='?', type=int, default=100,
                        help='EPIC Kitchens'' version, should be either "55" (first version) or "100" '
                             '(extended version). Default is 100')
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
                        help='Specify participants IDs. You can specif a single participant, e.g. --participants 1 or'
                             'a comma-separated list of them, e.g. --participants 1,2,3')
    parser.add_argument('--extension_only', nargs='?', type=bool, default=False, help='Download extension only')

    args = parser.parse_args()

    what = ('videos', 'rgb_frames', 'flow_frames', 'object_detection_images', 'consent_forms') if args.what is None \
        else args.what

    downloader_cls = Epic55Downloader if args.version == 55 and not args.extension_only else Epic100Downloader
    downloader = downloader_cls(base_output=args.output_path)
    downloader.extension_only = True
    downloader.download(what=what, participants=args.participants)
