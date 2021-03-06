#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Testcases:
# Buffy the Vampire Slayer  2930    terminated
# Better call Saul          37780   not started
# Homeland                  27811   running

# Imports
import argparse
from collections import OrderedDict
import datetime
import os
import re
import shutil
import sys
import tempfile
import urllib.request, urllib.parse
from xml.etree import ElementTree

# Constants
SCRIPT_NAME             = os.path.splitext(os.path.basename(__file__))[0] # removes the extension of the current script name
TVRAGE_API              = "http://services.tvrage.com/feeds/"
TVRAGE_SEARCH_API       = TVRAGE_API + "search.php?show="
TVRAGE_SHOWINFO_API     = TVRAGE_API + "showinfo.php?sid="
TVRAGE_EPISODE_LIST_API = TVRAGE_API + "episode_list.php?sid="
TVRAGE_FULL_SHOW_INFO   = TVRAGE_API + "full_show_info.php?sid="
STORAGE_DIR             = os.path.join(os.path.expanduser("~"), "." + SCRIPT_NAME)
STORAGE_DIR_NAME        = os.path.join(STORAGE_DIR, "name") # Used to display lists in alphabetical order
STORAGE_DIR_ID          = os.path.join(STORAGE_DIR, "id")
CACHE_DIR               = os.path.join(tempfile.gettempdir(), SCRIPT_NAME)
CACHE_DIR_RESEARCH      = os.path.join(CACHE_DIR, "research")
CACHE_DIR_SHOWS         = os.path.join(CACHE_DIR, "shows")
CACHE_LIFETIME          = datetime.timedelta(days=1)

# Arguments
parser = argparse.ArgumentParser(description="Manage TV shows")
group  = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-s",   "--search",           metavar="title",        help="Search a TV show")
group.add_argument("-i",   "--info",             metavar="id", type=int, help="Get information on a show")
group.add_argument("-le",  "--list-episodes",    metavar="id", type=int, help="List the episodes of a show")
group.add_argument("-ne",  "--next-episode",     metavar="id", type=int, help="Find the air date of the next episode")
group.add_argument("-pe",  "--previous-episode", metavar="id", type=int, help="Find the air date of the previous episode")
group.add_argument("-c",   "--check",            action="store_true",    help="Check if there are new episodes for the followed shows")
group.add_argument("-f",   "--follow",           metavar="id", type=int, help="Follow a show")
group.add_argument("-u",   "--unfollow",         metavar="id", type=int, help="Unfollow a show")
group.add_argument("-lf",  "--list-followed",    action="store_true",    help="List the followed shows")
group.add_argument("-r",   "--refresh",          metavar="id", type=int, help="Refresh the cached version of a TV show")
group.add_argument("-x",   "--clear-cache",      action="store_true",    help="Clear the temporary cache")
parser.add_argument("-gu", "--generate-url",     metavar="url",          help="Generate a query string for the site supplied as argument (works with -le, -ne and -c)")
parser.add_argument("-d",  "--delay",            metavar="days", type=int, default=0, help="Will look for the episodes within a delay of 'days' (works with -le, -ne and -c). Default: %(default)s")
parser.add_argument("-sd", "--strict_delay",     action="store_true",    help="Will look for the episodes with a delay of exactly 'delay' days (works with -le, -ne and -c)")
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

glob_internet_connection_available = False
def internet_connection_available():
    """
        Check if an internet connection is available.
        :return: True if an internet connection is available
    """
    global glob_internet_connection_available

    if not glob_internet_connection_available:
        try:
            urllib.request.urlopen("http://google.com", timeout=1) # Google should always be available
            glob_internet_connection_available = True
        except urllib.URLError:
            pass

    return glob_internet_connection_available

def get_root(cache_dir, url, parameter):
    """
        Return the root element of an XML document gathered from the TVRage API or from the cache if the document exists.
        If it downloads the document, it adds it to the cache.
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
            if (datetime.datetime.fromtimestamp(os.path.getmtime(permanent_cache_file_name)).date() + CACHE_LIFETIME <= datetime.datetime.today().date()
                and internet_connection_available()):
                urllib.request.urlretrieve(url + parameter, permanent_cache_file_name)
            cache_file_name = permanent_cache_file_name

    if not cache_file_name: # if not found in the permanent cache, check the temporary cache
        cache_file_name = os.path.join(cache_dir, parameter)
        if (not os.path.exists(cache_file_name)
            or (datetime.datetime.fromtimestamp(os.path.getmtime(cache_file_name)).date() + CACHE_LIFETIME <= datetime.datetime.today().date()
            and internet_connection_available())): # download from the web if not in any cache
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
    genres = root.find("genres")
    ret["genres"]  = genres and [genre.text for genre in genres.findall("genre") if genre.text is not None] or []
    ret["totalseasons"] = root.find("totalseasons").text

    return ret

def list_episodes(ident):
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

def step_episode(ident, delay=0, strict_delay=False, reverse=False):
    ident = str(ident)
    root  = get_root(CACHE_DIR_SHOWS, TVRAGE_FULL_SHOW_INFO, ident)
    ret   = {}
    ret["name"] = root.find("name").text

    if ret["name"] is None:
        raise ValueError("Invalid identifier")

    ret["status"] = root.find("status").text
    delay         = reverse and -delay or delay
    comp_date     = datetime.datetime.today().date() + datetime.timedelta(days=delay)
    episode_list  = root.find("Episodelist")
    if episode_list is not None:

        seasons = reverse and reversed(episode_list.findall("Season")) or episode_list.findall("Season")
        for season in seasons:

            episodes = reverse and reversed(season.findall("episode")) or season.findall("episode")
            for episode in episodes:
                str_air_date = episode.find("airdate").text
                try:
                    air_date     = datetime.datetime.strptime(str_air_date, "%Y-%m-%d").date()

                    if ((not reverse and not strict_delay and air_date >= comp_date)
                        or (reverse and not strict_delay and air_date <= comp_date)
                        or (strict_delay and air_date == comp_date)):

                        ret["season"]   = season.get("no")
                        ret["number"]   = episode.find("seasonnum").text.lstrip("0")
                        ret["title"]    = episode.find("title").text
                        ret["air_date"] = str_air_date
                        return ret
                except ValueError:
                    pass
    return ret

def next_episode(ident, delay=0, strict_delay=False):
    return step_episode(ident, delay, strict_delay)

def previous_episode(ident, delay=0, strict_delay=False):
    return step_episode(ident, delay, strict_delay, True)

def check_followed_shows(delay=0, strict_delay=False):
    """
        Generate the next episode for each show, in a specified delay.
        :param delay: If 0, check the next date for the shows starting from today, if 1, starting from tomorrow, if -1, starting from yesterday, etc.
        :param strict_delay: If True, return the shows whose next episode is in exactly delay days
        :return: A dict on the format { "name": episode_name, number": episode_number, "title": episode_title, "air_date": episode_air_date } for each followed show
    """
    ret = {}

    for file_name in os.listdir(STORAGE_DIR_NAME):
        root = ElementTree.parse(os.path.join(STORAGE_DIR_NAME, file_name))
        next_episode_data = next_episode(root.find("showid").text, delay, strict_delay)

        if "number" in next_episode_data:
            ret["name"] = next_episode_data["name"]
            ret["number"]   = next_episode_data["number"]
            ret["title"]    = next_episode_data["title"]
            ret["air_date"] = next_episode_data["air_date"]
            ret["season"]   = next_episode_data["season"]
            yield ret

def follow(ident):
    """
        Follow a show.
        :param ident: The identifier of the show to follow
    """
    ident = str(ident)

    symlink_name = os.path.join(STORAGE_DIR_ID, ident)
    if os.path.exists(symlink_name):
        raise ValueError("You already follow this show")

    root = get_root(CACHE_DIR_SHOWS, TVRAGE_FULL_SHOW_INFO, ident)
    ret  = root.find("name").text

    if ret is None:
        raise ValueError("Invalid identifier")

    persistent_file_name = os.path.join(STORAGE_DIR_NAME, urllib.parse.quote_plus(ret.lower()))
    cache_file_name      = os.path.join(CACHE_DIR_SHOWS, ident)
    shutil.copyfile(cache_file_name, persistent_file_name)
    os.symlink(persistent_file_name, symlink_name)

    return ret

def unfollow(ident):
    ident = str(ident)

    symlink_name = os.path.join(STORAGE_DIR_ID, ident)
    if not os.path.exists(symlink_name):
        raise ValueError("You don't follow this show")

    root = get_root(CACHE_DIR_SHOWS, TVRAGE_FULL_SHOW_INFO, ident)
    ret  = root.find("name").text

    os.remove(os.readlink(symlink_name))
    os.remove(symlink_name)

    return ret

def list_followed():
    """
        List the followed shows.
    """
    ret = {}

    for file_entry in os.listdir(STORAGE_DIR_NAME):
        file_path = os.path.join(STORAGE_DIR_NAME, file_entry)
        root = ElementTree.parse(file_path)
        ret["id"]   = root.find("showid").text
        ret["name"] = root.find("name").text
        ret["link"] = root.find("showlink").text
        yield ret

def refresh(ident):
    ident = str(ident)
    permanent_cache_file_name = os.path.join(STORAGE_DIR_ID, ident)

    if not os.path.exists(permanent_cache_file_name):
        raise ValueError("You don't follow this show")

    urllib.request.urlretrieve(TVRAGE_FULL_SHOW_INFO + ident, permanent_cache_file_name)

def clear_cache():
    """Clear the cache folders"""
    remove_folder_content(CACHE_DIR_RESEARCH)
    remove_folder_content(CACHE_DIR_SHOWS)

def generate_url(url, name, season_number, episode_number):
    """
        Generate a url from the args.generate_url argument.
        Example:
        Homeland season 1 episode 12 with args.generate_url = "myAwesomeSite.com/?s=" will produce "myAwesomeSite.com/?s=Homeland+S01E12"
        :param url: The base url
        :param name: The name of the show
        :param season_number: The season number
        :param episode_number: The episode number
        :return: The formated url
    """
    return url + urllib.parse.quote_plus(name + " " + "S" + season_number.rjust(2, "0") + "E" + episode_number.rjust(2, "0"))

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
                print("Title: " + list_episodes["seasons"][season][episode]["title"].encode(sys.stdout.encoding, "replace").decode())
                print("Air date: " + list_episodes["seasons"][season][episode]["air_date"])
                if args.generate_url:
                    print("URL: " + generate_url(args.generate_url, list_episodes["name"], season, episode))
    except ValueError as e:
        print(e)

elif args.next_episode:
    try:
        next_episode = next_episode(args.next_episode, args.delay, args.strict_delay)
        if "number" in next_episode:
            print("Name: " + next_episode["name"])
            print("Next episode: " + next_episode["season"] + "x" + next_episode["number"].rjust(2, "0") + ", \"" + next_episode["title"].encode(sys.stdout.encoding, "replace").decode() + "\"" + ", " + next_episode["air_date"])
            if args.generate_url:
                print("URL: " + generate_url(args.generate_url, next_episode["name"], next_episode["season"], next_episode["number"]))
        else:
            print("No known next episode for " + next_episode["name"])
            print("Status: " + next_episode["status"])
    except ValueError as e:
        print(e)

elif args.previous_episode:
    try:
        previous_episode = previous_episode(args.previous_episode, args.delay, args.strict_delay)
        if "number" in previous_episode:
            print("Name: " + previous_episode["name"])
            print("Previous episode: " + previous_episode["season"] + "x" + previous_episode["number"].rjust(2, "0") + ", \"" + previous_episode["title"].encode(sys.stdout.encoding, "replace").decode() + "\"" + ", " + previous_episode["air_date"])
            if args.generate_url:
                print("URL: " + generate_url(args.generate_url, previous_episode["name"], previous_episode["season"], previous_episode["number"]))
        else:
            print("No known next episode for " + previous_episode["name"])
            print("Status: " + previous_episode["status"])
    except ValueError as e:
        print(e)

elif args.check:
    for data in check_followed_shows(args.delay, args.strict_delay):
        print("Name: " + data["name"])
        print("Next episode: " + data["season"] + "x" + data["number"].rjust(2, "0") + ", \"" + data["title"].encode(sys.stdout.encoding, "replace").decode() + "\"" + ", " + data["air_date"])
        if args.generate_url:
            print("URL: " + generate_url(args.generate_url, data["name"], data["season"], data["number"]))
        print()

elif args.follow:
    try:
        name = follow(args.follow)
        print("You now follow " + name)
    except ValueError as e:
        print(e)

elif args.unfollow:
    try:
        name = unfollow(args.unfollow)
        print("You don't follow " + name + " anymore")
    except ValueError as e:
        print(e)

elif args.list_followed:
    print("Id" + ("\t%-30s" % "Name") + "\tLink")
    for data in list_followed():
        print(data["id"] + ("\t%-30s" % data["name"]) + "\t" + data["link"])

elif args.refresh:
    try:
        refresh(args.refresh)
        print("Cache refreshed")
    except ValueError as e:
        print(e)

elif args.clear_cache:
    clear_cache()
    print("Temporary cache cleared")
