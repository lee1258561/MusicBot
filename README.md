# MusicBot
  ICB MusicBot
  
## Notes
  [ToDo](https://hackpad.com/ToDO-4zUPvo84Cr0) List  
  train data [drive](https://drive.google.com/open?id=0B6HG80vOD3w7NFdUbEUxQnBLRVk)
  
  
## Milestone 2 Demo
**(Important!) 目前只有中文輸入全面支援，英文輸入僅有User Simulator demo支援**  
有web的DM demo界面，但是log並不完整。DM CLI則有完整的訊息。

python2.7

Install required packages:  
`$ pip2 install -r requirements.txt`

### User Simulator CLI Demo :  
`$ python2 userSimulator.py`  
輸入格式以及範例請參考report_milestone2.pdf  

### Dialogue Management CLI Demo :   
**(Important!) Source Spotify API token**  
`$ . ./data/config.sh` 

Then run:  
`$ python2 Dialogue_Manager.py --auto_test`  
or  
`$ python2 Dialogue_Manager.py --stdin`  
輸入格式以及範例請參考report_milestone2.pdf  

### Web Interface Dialogue Management Demo:  
**(Important!) User friendly interface, but the DM logs may not as complete as the CLI one above**  
**(Important!) Source Spotify API token**  
`$ . ./data/config.sh`  

Go to `chat/` directory, then run:  
`$ python2 chatdemo.py`  
會跑在本機的8888 port  

