#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# FIXME: Encoding problem on Windows when trying to display UTF-8 chars (ex: python .\tvs.py -le 25056) "'charmap' codec can't encode character '\u2019' in position 12: character maps to <undefined>"

# TODO: document all the functions
# TODO: last_episode
# TODO: allow parameters (delay and strict_delay) to the --check command

# Testcases:
# Buffy the Vampire Slayer  2930    terminated
# Better call Saul          37780   not started
# Homeland                  27811   running

# Imports
import argparse
from collections import OrderedDict
import datetime
import os
import shutil
import sys
import tempfile
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ElementTree

# Constants
SCRIPT_NAME             = os.path.splitext(os.path.basename(__file__))[0]
TVRAGE_API              = "http://services.tvrage.com/feeds/"
TVRAGE_SEARCH_API       = TVRAGE_API + "search.php?show="
TVRAGE_SHOWINFO_API     = TVRAGE_API + "showinfo.php?sid="
TVRAGE_EPISODE_LIST_API = TVRAGE_API + "episode_list.php?sid="
TVRAGE_FULL_SHOW_INFO   = TVRAGE_API + "full_show_info.php?sid="
STORAGE_DIR             = os.path.join(os.path.expanduser("~"), "." + SCRIPT_NAME)
STORAGE_DIR_NAME        = os.path.join(STORAGE_DIR, "name")
STORAGE_DIR_ID          = os.path.join(STORAGE_DIR, "id")
CACHE_DIR               = os.path.join(tempfile.gettempdir(), SCRIPT_NAME)
CACHE_DIR_RESEARCH      = os.path.join(CACHE_DIR, "research")
CACHE_DIR_SHOWS         = os.path.join(CACHE_DIR, "shows")

# Arguments
parser = argparse.ArgumentParser(description="Manage TV shows")
group  = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-s",  "--search",        metavar="title",        help="Search a TV show")
group.add_argument("-i",  "--info",          metavar="id", type=int, help="Get information on a show")
group.add_argument("-le", "--list-episodes", metavar="id", type=int, help="List the episodes of a show")
group.add_argument("-ne", "--next-episode",  metavar="id", type=int, help="Find the air date of the next episode")
group.add_argument("-c",  "--check",         action="store_true",    help="Check if there are new episodes for the followed shows")
group.add_argument("-f",  "--follow",        metavar="id", type=int, help="Follow a show")
group.add_argument("-u",  "--unfollow",      metavar="id", type=int, help="Unfollow a show")
group.add_argument("-lf", "--list-followed", action="store_true",    help="List the followed shows")
group.add_argument("-r",  "--refresh",       metavar="id", type=int, help="Refresh the cached version of a TV show")
group.add_argument("-x",  "--clear-cache",   action="store_true",    help="Clear the cache")
parser.add_argument("-gu", "--generate-url", metavar="url",          help="Generate a query string for the site supplied as argument")
if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)
args = parser.parse_args()

# Utility functions
def remove_folder_content(folder_path):
    """
        Remove all the content of a folder.
        :param folder_path: The path of the folder to empty
    """
    for cache_file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, cache_file)

        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)

        except Exception as e:
            print(e)

def get_root(cache_dir, url, parameter):
    """
        Return the root element of an XML document gathered from the TVRage API or from
        the cache if the document exists. If it downloads the document, it adds it to
        the cache.
        :param cache_dir: The cache directory to search for the asked document.
        :param url: The URL from where to download the document if it's not cached.
        :param parameter: The parameter to add to the URL.
        :return: The root element of an XML document representing the show passed as parameter.
    """
    parameter = urllib.parse.quote_plus(parameter.lower())
    cache_file_name = ""

    if cache_dir == CACHE_DIR_SHOWS: # check the permanent cache
        permanent_cache_file_name = os.path.join(STORAGE_DIR_ID, parameter)
        if os.path.exists(permanent_cache_file_name):
            cache_file_name = permanent_cache_file_name

    if not cache_file_name: # if not found in the permanent cache, check the temporary cache
        cache_file_name = os.path.join(cache_dir, parameter)
        if not os.path.exists(cache_file_name): # download from the web if not in any cache
            urllib.request.urlretrieve(url + parameter, cache_file_name)

    root = ElementTree.parse(cache_file_name)
    return root

# Script functions
def init():
    """Create the cache and storage folders."""
    if not os.path.exists(CACHE_DIR_RESEARCH):
        os.makedirs(CACHE_DIR_RESEARCH)

    if not os.path.exists(CACHE_DIR_SHOWS):
        os.makedirs(CACHE_DIR_SHOWS)

    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)
        if os.name == "nt":
            os.popen("attrib +h " + STORAGE_DIR).close()

    if not os.path.exists(STORAGE_DIR_NAME):
        os.makedirs(STORAGE_DIR_NAME)

    if not os.path.exists(STORAGE_DIR_ID):
        os.makedirs(STORAGE_DIR_ID)

def search(name):
    root = get_root(CACHE_DIR_RESEARCH, TVRAGE_SEARCH_API, name)
    ret  = OrderedDict()

    for show in root.findall("show"):
        ret[show.find("showid").text] = [show.find("name").text, show.find("link").text]

    return ret;

def info(ident):
    ident = str(ident)
    root  = get_root(CACHE_DIR_SHOWS, TVRAGE_FULL_SHOW_INFO, ident)
    ret   = {}
    ret["name"] = root.find("name").text

    if ret["name"] is None:
        raise ValueError("Invalid identifier")

    ret["started"] = root.find("started").text
    ret["status"]  = root.find("status").text
    ret["genres"]  = [genre.text for genre in root.find("genres").findall("genre") if genre.text is not None]
    ret["totalseasons"] = root.find("totalseasons").text

    return ret

def list_epilsodes(ident):
    ident = str(ident)
    root  = get_root(CACHE_DIR_SHOWS, TVRAGE_FULL_SHOW_INFO, ident)
    ret   = {}
    ret["name"]   = root.find("name").text
    ret["status"] = root.find("status").text

    if ret["name"] is None:
        raise ValueError("Invalid identifier")

    episode_list = root.find("Episodelist")
    if episode_list is not None:
        ret["seasons"] = OrderedDict()

        for season in episode_list.findall("Season"):
            season_number = season.get("no")
            ret["seasons"][season_number] = OrderedDict()

            for episode in season.findall("episode"):
                episode_number = episode.find("seasonnum").text.lstrip("0")
                ret["seasons"][season_number][episode_number] = {}
                ret["seasons"][season_number][episode_number]["title"] = episode.find("title").text
                ret["seasons"][season_number][episode_number]["air_date"] = episode.find("airdate").text

    return ret

def next_episode(ident, delay=0, strict_delay=False):
    ident = str(ident)
    root  = get_root(CACHE_DIR_SHOWS, TVRAGE_FULL_SHOW_INFO, ident)
    ret   = {}
    ret["name"]   = root.find("name").text
    ret["status"] = root.find("status").text

    if ret["name"] is None:
        raise ValueError("Invalid identifier")

    comp_date = datetime.datetime.today().date() + datetime.timedelta(days=delay)
    episode_list = root.find("Episodelist")
    if episode_list is not None:

        for season in episode_list.findall("Season"):

            for episode in season.findall("episode"):
                str_air_date = episode.find("airdate").text
                air_date     = datetime.datetime.strptime(str_air_date, "%Y-%m-%d").date()

                if (not strict_delay and air_date >= comp_date) or (strict_delay and air_date == comp_date):
                    ret["season"]   = season.get("no")
                    ret["number"]   = episode.find("seasonnum").text.lstrip("0")
                    ret["title"]    = episode.find("title").text
                    ret["air_date"] = str_air_date
                    return ret
    return ret

def check_followed_shows(delay=0, strict_delay=False):
    """
        Return the next episode for each show, in a specified delay.
        :param delay: If 0, check the next date for the shows starting from today, if 1, starting from tomorrow, if -1, starting from yesterday, etc.
        :param strict_delay: If True, return the shows whose next episode is in exactly delay days.
        :return: A dict on the format { episode_name: { "number": episode_number, "title": episode_title, "air_date": episode_air_date }, ... }
    """
    ret = {}
    for file_name in os.listdir(STORAGE_DIR_NAME):
        root = ElementTree.parse(os.path.join(STORAGE_DIR_NAME, file_name))
        next_episode_data = next_episode(root.find("showid").text, delay, strict_delay)

        if "number" in next_episode_data:
            ret[next_episode_data["name"]] = {}
            ret[next_episode_data["name"]]["number"]   = next_episode_data["number"]
            ret[next_episode_data["name"]]["title"]    = next_episode_data["title"]
            ret[next_episode_data["name"]]["air_date"] = next_episode_data["air_date"]
            ret[next_episode_data["name"]]["season"]   = next_episode_data["season"]

    return ret

def follow(ident):
    """
        Follow a show.
        :param ident: The identifier of the show to follow
    """
    ident = str(ident)

    symlink_name = os.path.join(STORAGE_DIR_ID, ident)
    if os.path.exists(symlink_name):
        raise ValueError("You already follow this show")

    root  = get_root(CACHE_DIR_SHOWS, TVRAGE_FULL_SHOW_INFO, ident)
    ret   = root.find("name").text

    if ret is None:
        raise ValueError("Invalid identifier")

    persistent_file_name = os.path.join(STORAGE_DIR_NAME, urllib.parse.quote_plus(ret.lower()))
    cache_file_name      = os.path.join(CACHE_DIR_SHOWS, ident)
    shutil.copyfile(cache_file_name, persistent_file_name)
    os.symlink(persistent_file_name, symlink_name)

    return ret

def unfollow():
    pass

def list_followed():
    """
        List the followed shows.
    """
    ret = {}

    for file_entry in os.listdir(STORAGE_DIR_NAME):
        file_path = os.path.join(STORAGE_DIR_NAME, file_entry)
        root = ElementTree.parse(file_path)
        ret[root.find("showid").text] =  [root.find("name").text, root.find("showlink").text]

    return ret

def refresh():
    pass

def clear_cache():
    """Clear the cache folders"""
    remove_folder_content(CACHE_DIR_RESEARCH)
    remove_folder_content(CACHE_DIR_SHOWS)

def generate_url(url, name, season_number, episode_number):
    """
        Generate a url from the args.generate_url argument.
        example :
        Homeland season 1 episode 12 with args.generate_url = 'myAwesomeSite.com/?s='
        will produce 'myAwesomeSite.com/?s=Homeland+S01E12'
        :param url: The base url
        :param name: The name of the show
        :param season_number: The season #
        :param episode_number: The episode #
        :return: The formated url
    """
    url += name + "+" + "S"+ season_number.rjust(2,'0') + "E" + episode_number.rjust(2,'0')
    return url

# Main
init()

if args.search:
    search = search(args.search)
    print("Id" + ("\t%-30s" % "Name") + "\tLink")
    for ident, data in list(search.items()):
        print(ident + ("\t%-30s" % data[0]) + "\t" + data[1])

elif args.info:
    try:
        info = info(args.info)
        print("Name: " + info["name"])
        print("Premiere: " + info["started"])
        print("Status: " + info["status"])
        print("Genre: " + ", ".join(info["genres"]))
        print("Seasons: " + info["totalseasons"])
    except ValueError as e:
        print(e)

elif args.list_episodes:
    try:
        list_episodes = list_episodes(args.list_episodes)
        print("Name: " + list_episodes["name"])
        for season in list_episodes["seasons"]:
            print("Season: " + season)
            for episode in list_episodes["seasons"][season]:
                print("Number: " + episode)
                print("Title: " + list_episodes["seasons"][season][episode]["title"])
                print("Air date: " + list_episodes["seasons"][season][episode]["air_date"])
                if args.generate_url:
                    url = generate_url(args.generate_url, list_episodes["name"], season, episode)
                    print("url: " + url)
    except ValueError as e:
        print(e)

elif args.next_episode:
    try:
        next_episode = next_episode(args.next_episode)
        if "number" in next_episode:
            print("Name: " + next_episode["name"])
            print("Next episode: #" + next_episode["number"] + ", \"" + next_episode["title"] + "\"" + ", " + next_episode["air_date"])
            if args.generate_url:
                url = generate_url(args.generate_url, next_episode["name"], next_episode["season"], next_episode["number"])
                print("url: " + url)
        else:
            print("No known next episode for " + next_episode["name"])
            print("Status: " + next_episode["status"])
    except ValueError as e:
        print(e)

elif args.check:
    check = check_followed_shows()
    for name, data in list(check.items()):
        print("Name: " + name)
        print("Next episode: #" + data["number"] + ", \"" + data["title"] + "\"" + ", " + data["air_date"])
        if args.generate_url:
            url = generate_url(args.generate_url, name, data["season"], data["number"])
            print("url: " + url)

elif args.follow:
    try:
        name = follow(args.follow)
        print("You now follow " + name)
    except ValueError as e:
        print(e)

elif args.unfollow:
    unfollow()

elif args.list_followed:
    list_followed = list_followed()
    print("Id" + ("\t%-30s" % "Name") + "\tLink")
    for ident, data in list(list_followed.items()):
        print(ident + ("\t%-30s" % data[0]) + "\t" + data[1])

elif args.refresh:
    refresh()

elif args.clear_cache:
    clear_cache()
    print("Cache cleared")
