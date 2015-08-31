#!/usr/bin/env python

import os
import shutil
import subprocess
import argparse
import re
import json
from collections import defaultdict

import eyed3

parser = argparse.ArgumentParser(description='Copy audio library to USB')
parser.add_argument('-c', '--config', help='Config file', required=False, default=None)
parser.add_argument('-s', '--source', help='Path to audio lib', required=False, default='.')
parser.add_argument('-d', '--dest', help='USB mount point', required=False, default='/Volumes/MUSIC')
parser.add_argument('-t', '--tmpdir', help='tmp directory', required=False, default='tmp')
parser.add_argument('-a', '--album_chars', help='Number of characters in album name to display',
                    required=False, default=None)
args = parser.parse_args()

if args.config:
    assert os.path.exists(args.config), 'Config file not found!'
    with open(args.config, 'r') as fh:
        config = defaultdict(lambda: None, json.load(fh))
else:
    config['source'] = args.path.realpath(args.source)
    config['dest'] = os.path.realpath(args.dest)
    config['tmpdir'] = os.path.realpath(args.tmpdir)
    config['album_chars'] = None

for dirname in ('source', 'dest'):
    config[dirname] = os.path.realpath(config[dirname])
    assert os.path.exists(config[dirname]), '{} not found!'.format(dirname)

config['tmpdir'] = os.path.realpath(config['tmpdir'])
if os.path.exists(config['tmpdir']):
    if raw_input('tmp directory exists - okay to delete? [y/N]: ').lower() != 'y':
        quit()
    shutil.rmtree(os.path.realpath(config['tmpdir']))

# aggregate track paths by artist, album, and track no
srcfiles = [os.path.realpath(os.path.join(dirpath, f))
            for dirpath, dirnames, files in os.walk(config['source'])
            for f in files if f.endswith(('.mp3', '.aac'))]


def meta_to_artist_title_album_track(m):
    def strip(s):
        return s.replace('/', '-').replace('"', '').encode('ascii', 'ignore')

    artist = m.tag.album_artist if m.tag.album_artist else m.tag.artist
    artist = strip(re.sub('^[tT]he ', '', artist))
    title = strip(m.tag.title)
    album = strip(m.tag.album)
    order = m.tag.track_num[0]

    # strip disc num out of album name, and add a big number to the track num
    # for multi-disc albums.  The  number isn't important since we'll re-sort
    # everything below when making symlinks - we just want to keep the tracks
    # in order across albums
    disc_num_matches = re.findall(' .?[Dd]is[ck] [0-9]+.?', album)
    if len(disc_num_matches) > 0:
        disc_str = disc_num_matches[0]
        album = album.replace(disc_str, '')
        disc_num = int(re.findall('[0-9]+', disc_str)[0])
        order += disc_num * 1000
    elif m.tag.disc_num[0]:
        order += m.tag.disc_num[0] * 1000

    return artist, album, title, order

artist_album_to_tracks = defaultdict(list)
for f in srcfiles:
    try:
        m = eyed3.load(f)
        artist, album, track, order = meta_to_artist_title_album_track(m)
    except Exception as e:
        print e

    for key, ignore_dict in (('artist_ignore', artist), ('album_ignore', album), ('genre_igore', m.tag.genre)):
        if config[ignore_dict] and key in config[ignore_dict]:
            break
    else:
        print 'processing', artist, album, track
        artist_album_to_tracks[(artist, album)].append((order, track, f.encode('ascii', 'ignore')))

# create a tmp directory with symlinks to the tracks organized the way we want
# it on the USB stick - that will allow us to use rsync to to copy/update
for artist, album in artist_album_to_tracks:
    for i, (track, name, path) in enumerate(sorted(artist_album_to_tracks[(artist, album)])):
        # one folder per artist, with first N chars of album name prepended
        # to each song, followed by sort order and track name.  This
        # will allow us to sort by album, and still see a bit of the track name
        fn = '{album}-{track:02d}-{name}.{ext}'.format(album=album[:config['album_chars']],
                                                       track=i + 1,
                                                       name=name,
                                                       ext=path.split('.')[-1])
        dst = os.path.join(config['tmpdir'], artist, fn)
        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
        os.system('ln -s "{src}" "{dst}"'.format(src=path, dst=dst))

os.system('cd "{tmp}"; rsync -arLv . "{dst}" --delete'.format(tmp=config['tmpdir'],
                                                               dst=config['dest']))

# here's the gross part - we have to sort the files in the FAT32 filesystem
# to make sure they are displayed properly.  The fatsort utility will do this,
# but requires sudo
print 'Please enter your password to sort files on the USB stick'
cmd = 'diskutil unmount {dest}'.format(dest=config['dest'])
stdout, _ = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()
device = re.match('Volume.* on ([a-zA-Z0-9]+) unmounted', stdout).groups()[0]
os.system('sudo fatsort /dev/{device}'.format(device=device))

# clean up and go home
shutil.rmtree(config['tmpdir'])

