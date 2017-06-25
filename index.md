# MusicBot: A Smart Music Assistant
*Demo Link: http://140.112.90.203:8888*  
## Overview
### Flow Chart
![Flow](http://i.imgur.com/qa9F7Xk.png)

### Features
* Play songs: Search songs with artist or track name
* Recommendation: Given the artist / track name or genre, recommending songs
* Information: Given the artist or track name, providing information
* Playlist: 
    * Create a playlist named by user
    * Add songs to the specific playlist
    * Play the specific playlist
* Play Public Playlist: Play some public playlist like "Taiwan Top 50 Music" or "Music for study" provided by Spotify Charts

## Ontology
### Spotify API
Supporting features like searching for a song, recommending songs by related information, listing popular songs, and accessing user’s playlist. Providing access to over 30 million songs, including almost all the Taiwanese pop music which our target audience want to listen to.
![Database Sheets](http://i.imgur.com/MXiJvpA.png)

## Dialogue Management
### Dialogue State Tracking
* Dialogue state: determined by the action and distribution state of last time step, the current user response, and the confirm state

### Dialogue Policy
* Action: confirm, question, response, and info
* Policy: setting upper and lower threshold deciding whether to confirm / asking questions if needing information / Response and info represent the end of a conversation.

### User Simulator
* Simulator Goal: Complete the user goal which is random inited at the beginning
* Simulator Response: Response the agent’s actions such as requirement or confirmation based on templates. 
* Error Handling: User simulator would check if the agent’s action is valid or not. For the agent asking some invalid slots or confirming for wrong slots, it would give a negative response.

### Success Rate:
#### Rule-based: 96% 
#### RL-based: 20%
![](http://i.imgur.com/M1qPvmq.png)

## Language Understanding
### Model Architecture
* Attention-based sequence-to-sequence model (Bidirectional RNN), which can Jointly learn intent detection and slot filling
![](http://i.imgur.com/iriaZl0.png)

### Data Collection
* Several templates for each intents
* Parsing data from Spotify API to fit into the slots
* Balancing the number of data for each template

### Training / Testing size
* Training: 159299 sentences / Testing: 8850 sentences

### Performance
* Perplexity: almost 1 (Training & Validation Set)
* Testing on real human: 85% accuracy for LU

### Rule-Based LU
* Directly check if the input sentence satisfies some kind of rules or whether some slots in DB are in the input sentence

## Natural Language Generation
### Model Architecture
* Seq2seq model
* Input: mapping semantic frames into a one hot sequence 
* Output: sentence template we want to generate
* The model first encode the one hot sequence of the frames, then decoder decode the encoding and output the template of sentence.

### Data Collection
* For each possible semantic frame, we collected corresponding template from real human.
* To provide different responses given identical semantic frame, we collected at least three different templates for each frames.

### Training / Testing size
Training: 155 templates  /  Testing: 20 templates

### Performance
Training: 0.88  /  Testing: 0.34 (BLEU score)
![model](http://i.imgur.com/lByB2ed.png)
