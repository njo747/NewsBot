import os
import sys
import json

import requests
from flask import Flask, request
import feedparser
import re
import math
import random
import urllib2
from newspaper import Article

app = Flask(__name__)
# Current user preferences
dictionary = dict()
# Payload string
payloadFinal = ""
# Dictionary to contain info about the news. title = {link : image}
ultraDictOfNews = dict()
imageURL = ""
timeToRead = None
searchQuery = ""
booledSearch = False
booledTime = False

@app.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route('/', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events
    data = request.get_json()
    log(data)
    global searchQuery
    global booledSearch
    global booledTime
    global timeToRead  # you may not want to log every incoming message in production, but it's good for testing

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):  # someone sent us a message
                    # TODO: Fix payload being detected and sent into query properly
                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    message_text = messaging_event["message"]["text"]
                    if not booledSearch:
                        log("is this {bool}".format(bool = booledSearch))
                        searchQuery = message_text
                        booledSearch = True
                        send_message(sender_id, "Sure, I'll find some %s articles for you!" % searchQuery)
                        send_message(sender_id, "Choose how much time you have to read! (in minutes)")  # the message's text
                    elif not booledTime and booledSearch:
                        booledTime = True
                        timeToRead = int(message_text)
                        if (timeToRead <= 5):
                            send_message(sender_id, "You have %i minutes to read? That's short! Anyway, here you go!" % timeToRead)
                            result = send_feed(searchQuery, timeToRead)
                            send_message(sender_id, result)
                            send_quick_reply(sender_id)
                        # To fix sending the generic template
                        # send_generic_template(sender_id)
                        elif (timeToRead > 5):
                            send_message(sender_id, "Alright, get ready for a long read!")
                            result = send_feed(searchQuery, timeToRead)
                            send_message(sender_id, result)
                            send_quick_reply(sender_id)
                    else:
                        send_message(sender_id, "I don't really understand you... :(")

                elif messaging_event.get("delivery"):  # delivery confirmation
                    pass

                elif messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    received_postback(messaging_event)

                elif messaging_event.get("message").get("quick_reply"):
                    received_quick_reply(messaging_event)

                else:
                    log("Webhook return unknown event " + messaging_event)

    return "ok", 200


def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)

def received_postback(event):
    sender_id = event["sender"]["id"]
    recipient_id = event["recipient"]["id"]
    payload = event["postback"]["payload"]
    log("received postback from {recipient} with payload {payload}".format(recipient = recipient_id, payload = payload))
    if payload == "Get Started":
        send_message(sender_id, "Welcome to NewsBot! What do you want to read about today?")
    else:
        send_message(sender_id, "Postback recieved")
# TODO: Fix up this method call to send carousels as well. (sending template)

def received_quick_reply(event):
    sender_id = event["sender"]["id"]
    recipient_id = event["recipient"]["id"]
    payload = event["message"]["quick_reply"]["payload"]
    log("Received quick reply!")
    if payload == "next":
        randomKey = random.choice(ultraDictOfNews.keys())
        linkToArticle = ultraDictOfNews[randomKey]['link']
        stringResult = "This article is %.1f minute(s): %s (Link: %s)" % (ultraDictOfNews[randomKey]['time'], randomKey, linkToArticle)
        del ultraDictOfNews[randomKey]
        send_message(sender_id, stringResult)

    elif payload == "search":
        booledSearch = False
        ultraDictOfNews.clear()
        send_message(sender_id, "Alright, let's search for something else!")
        send_message(sender_id, "What would you like to search for?")

    elif payload == "change":
        booledTime = False
        ultraDictOfNews.clear()
        send_message(sender_id, "You'd like to change your read time eh?")
        send_message(sender_id, "Enter the new amount of time you'd like to spend reading!")


def send_postback_button(recipient_id):
    log("sending postback message to {recipient}".format(recipient = recipient_id))
    data = json.dumps({
        "message": {
            "attachment": {
                "payload": {
                    "buttons": [
                    {   
                        "payload": "Tech",
                        "type": "postback",
                        "title": "Tech"
                    },
                {
                    "payload": "Politics",
                    "title": "Politics",
                    "type": "postback"
                }, 
                { "payload": "Global Affairs",
                  "title": "Global Affairs",
                  "type": "postback"
                },
            ],
            "template_type": "button",
            "text": "What categories are you interested in?"
          },
          "type": "template"
        }
      },
      "recipient": {
        "id": recipient_id
      }
    })
    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)

def send_quick_reply(recipient_id):
    log("sending quick_reply to {recipient}".format(recipient = recipient_id))
    data = json.dumps({
        "recipient": {
            "id":recipient_id
        },
        "message":{
            "text":"Done reading? What next?",
            "quick_replies":[
                {
                    "content_type":"text",
                    "title":"Next Article",
                    "payload":"next"
                },
                {
                    "content_type":"text",
                    "title":"Change Search Value",
                    "payload":"search"
                },
                {
                    "content_type":"text",
                    "title":"Change Reading Time",
                    "payload":"change"
                }
            ]
        }
    })
    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)

def read_time(link):
    articleLink = Article(link)
    articleLink.download()
    articleLink.parse()
    global topImage
    topImage = articleLink.images[0]
    articleText = articleLink.text
    splitText = articleText.strip().split(" ")
    if (len(splitText) <= 275.0):
        return 1.0
    else:
        answer = math.ceil(len(splitText) / 275.0)
        return answer
# TODO: Update send_feed with new entries for the post (currently 0 is placeholder for image values (fix regex)
def send_feed(payload, timeToRead):
    rssFeed = feedparser.parse("https://news.google.com/news/section?q=%s&output=rss" % re.sub(r"\s", "", payload))
    for post in rssFeed.entries:
        totalRead = read_time(post.link)
        if (totalRead <= timeToRead):
            try:
                imageURL = topImage
            except urllib2.HTTPError:
                imageURL = 0
            ultraDictOfNews[post.title] = {'time':totalRead, 'image':imageURL, 'link':post.link}
    randomKey = random.choice(ultraDictOfNews.keys())
    linkToArticle = ultraDictOfNews[randomKey]['link']
    stringResult = "This article is %.1f minute(s): %s (Link: %s)" % (ultraDictOfNews[randomKey]['time'], randomKey, linkToArticle)
    del ultraDictOfNews[randomKey]
    return stringResult

def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()


if __name__ == '__main__':
    app.run(debug=True)