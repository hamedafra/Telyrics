import sys
import re
import string
import html
import math
import telepot
import telepot.helper
import spotipy
import urllib.request, urllib.error, urllib.parse
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.delegate import (
    per_chat_id, create_open, pave_event_space, include_callback_query_chat_id)
propose_records = telepot.helper.SafeDict()  # thread-safe dict
spotify = spotipy.Spotify()

class lyrics(telepot.helper.ChatHandler):
   
    def __init__(self, *args, **kwargs):
        super(lyrics, self).__init__(*args, **kwargs)
        # Retrieve from database
        global propose_records
        if self.id in propose_records:
            self._edit_msg_ident = propose_records[self.id]
            self._editor = telepot.helper.Editor(self.bot, self._edit_msg_ident) if self._edit_msg_ident else None
        else:
            self._edit_msg_ident = None
            self._editor = None
    def open(self, initial_msg, seed):
        self.sender.sendMessage('Enter a search query to continue...')
        #return True  # prevent on_message() from being called on the initial message
    def on_chat_message(self , msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        search = msg['text']
        search.replace(" ", "+")   
        spotify = spotipy.Spotify()
        self._results  = spotify.search(q=search, type='track', limit='50')
        pages = math.ceil(len(self._results['tracks']['items'])/3)
        inlinekeyboards = []

        if pages == 1:
            for track in self._results['tracks']['items']:
                trackname = track['artists'][0]['name']+' -'+' '+ track['name']
                inlinekeyboards.append([InlineKeyboardButton(text=trackname, callback_data=track['uri'])])
                keyboard = InlineKeyboardMarkup(inline_keyboard=inlinekeyboards)
            self.print_search(keyboard,msg)
        elif pages >  1:
            for track in self._results['tracks']['items'][:3]:
                trackname = track['artists'][0]['name']+' -'+' '+ track['name']
                inlinekeyboards.append([InlineKeyboardButton(text=trackname, callback_data=track['uri'])])
            current = 1
            pagekeyboard = self.get_pagination(current,pages) 
            inlinekeyboards.append(pagekeyboard)
            keyboard = InlineKeyboardMarkup(inline_keyboard=inlinekeyboards)
            self.print_search(keyboard, msg)

    def get_pagination(self,current,pages):
        pagination = []
        if pages >4:
                printed = 0
                if current > 1 :
                        pagination.append(InlineKeyboardButton(text='«1', callback_data='page:1'))
                if current > 2 :
                        pagination.append(InlineKeyboardButton(text='‹'+str(current - 1), callback_data='page:'+str(current - 1)))
                pagination.append(InlineKeyboardButton(text='.'+str(current)+'.', callback_data='current:'+str(current)))
                printed = current
                for x in range(printed+1,4):
                        pagination.append(InlineKeyboardButton(text=str(x), callback_data='page:'+str(x)))
                        printed = x
                if current < pages - 1:
                        pagination.append(InlineKeyboardButton(text=str(printed + 1) +'›', callback_data='page:'+str(printed + 1)))
                if current < pages:
                        pagination.append(InlineKeyboardButton(text=str(pages)+'»', callback_data='page:'+str(pages)))

        else:
                for x in range(1, current):
                        pagination.append(InlineKeyboardButton(text=str(x), callback_data='page:'+str(x)))
                pagination.append(InlineKeyboardButton(text='.'+str(current)+'.', callback_data='current:'+str(current)))
                for x in range(current+1,pages+1):
                        pagination.append(InlineKeyboardButton(text=str(x), callback_data='page:'+str(x)))
        return pagination
        
    def print_search(self , keyboard,msg):
        sent = self.sender.sendMessage("Showing results for '"+msg['text']+"'", reply_markup=keyboard)
        self._editor = telepot.helper.Editor(self.bot, sent)
        self._edit_msg_ident = telepot.message_identifier(sent)
    def _cancel_last(self):
        if self._editor:
            self._editor.editMessageReplyMarkup(reply_markup=None)
            self._editor = None
            self._edit_msg_ident = None
    def on_callback_query(self, msg  ):
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')

        if 'page:' in query_data :

            current = re.findall('\d+', query_data)
            inlinekeyboards = []
            pages = math.ceil(len(self._results['tracks']['items']) / 3)
            index = (int(current[0]) - 1) * 3
            for track in self._results['tracks']['items'][index:index+3]:
                trackname = track['artists'][0]['name']+' -'+' '+ track['name']
                inlinekeyboards.append([InlineKeyboardButton(text=trackname, callback_data=track['uri'])])
            pagekeyboard = self.get_pagination(int(current[0]),pages)
            inlinekeyboards.append(pagekeyboard)
            keyboard = InlineKeyboardMarkup(inline_keyboard=inlinekeyboards)
            self._editor.editMessageReplyMarkup(reply_markup=keyboard)

        elif 'current:' not in query_data:

            results = spotify.track(query_data)
            print(results['external_urls'])
            sent = self.sender.sendMessage(results['external_urls']['spotify'])
            self._editor = telepot.helper.Editor(self.bot, sent)
            self._edit_msg_ident = telepot.message_identifier(sent)
            azlyrics = self.get_azlyrics(results['artists'][0]['name'], results['name'])
            wikia = self.get_wikia(results['artists'][0]['name'], results['name'])

            if azlyrics :
                self.sender.sendMessage(azlyrics)
            elif wikia:

                self.sender.sendMessage(wikia)

            else:

                self.sender.sendMessage("No lyrics found :(")

    def on__idle(self, event):
        self.sender.sendMessage('Session expired. Please try again')
        self.close()
    def on_close(self, ex):
        #Save to database
        global propose_records
        propose_records[self.id] = (self._edit_msg_ident)

    def remove_punctuation(self,data):
        for c in string.punctuation:
            data = data.replace(c, "")

            return data

    def get_azlyrics(self, artist, title):

        # remove unwanted characters from artist and title strings
        clean_artist = artist
        if clean_artist.startswith("the "):
            clean_artist = clean_artist[4:]
        clean_artist = clean_artist.replace(" ", "")
        clean_artist = self.remove_punctuation(clean_artist)
        clean_artist = clean_artist.lower()

        clean_title = title
        clean_title = clean_title.replace(" ", "")
        clean_title = self.remove_punctuation(clean_title)
        clean_title = clean_title.lower()

        # create lyrics Url
        url = "http://www.azlyrics.com/lyrics/" + clean_artist + "/" + clean_title + ".html"
        print("azlyrics Url " + url)
        try:
            resp = urllib.request.urlopen(url).read().decode('utf-8')

        except:
            print("could not connect to azlyrics.com")
            return ""


        start = resp.find("that. -->")
        if start == -1:
            print("lyrics start not found")
            return ""
        resp = resp[(start + 10):]
        end = resp.find("</div>")
        if end == -1:
            print("lyrics end not found ")
            return ""
        resp = resp[:(end - 1)]

        # replace unwanted parts
        resp = html.unescape(resp)
        resp = resp.replace("<br>", "")
        resp = resp.replace("<i>", "")
        resp = resp.replace("</i>", "")

        print (resp)

        lyrics = resp
        lyrics = string.capwords(lyrics, "\n").strip()

        return lyrics



    def get_wikia(self,artist, title):

        # format artist and title
        artist = artist.replace(" ", "_")
        title = title.replace(" ", "_")
        clean_artist = urllib.parse.quote(artist)
        clean_title = urllib.parse.quote(title)

        # create lyrics Url
        url = "http://lyrics.wikia.com/wiki/" + clean_artist + ":" + clean_title
        print("lyricwiki Url " + url)
        try:
            resp = urllib.request.urlopen(url).read().decode('utf-8')
        except:
            print("could not connect to lyricwiki.org")
            return ""

        # cut HTML source to relevant part
        start = resp.find("class='lyricbox'>")
        if start == -1:
            print("lyrics start not found")
            return ""
        resp = resp[(start + 17):]
        end = resp.find("<div class='lyricsbreak'>")
        if end == -1:
            print("lyrics end not found")
            return ""
        resp = resp[:end]

        # replace unwanted parts
        resp = html.unescape(resp)
        resp = resp.replace("<br>", "\n")
        resp = resp.replace("<br />", "\n")
        resp = resp.replace("<i>", "")
        resp = resp.replace("</i>", "")
        resp = re.sub("<a[^>]*>", "", resp)
        resp = resp.replace("</a>", "")

        resp = resp.strip()

        print (resp)
        lyrics = resp
        return lyrics


TOKEN = sys.argv[1]

bot = telepot.DelegatorBot(TOKEN, [
    include_callback_query_chat_id(
        pave_event_space())(
            per_chat_id(types=['private']), create_open, lyrics, timeout=3600),
])
bot.message_loop(run_forever='Listening ...')
