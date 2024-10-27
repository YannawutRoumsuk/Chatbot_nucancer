Python
1. Install the latest Python version or version 3.11.4
2. Create cerds.json file and replace it with the file obtained from Google APIs. You can see how to do this at: https://www.youtube.com/watch?v=ISOd3D7Oik0#t=7m37s
3. Go to userID() function in run.py file, at the line_bot_api parameter, replace it with the new channel access token
4. Run the run.py file
5. Install ngrok and use it to simulate a server using the command ngrok http 5000 in cmd (Note: You must register for ngrok before using it https://ngrok.com/)
6. Go to Dialogflow, navigate to fulfillment, and insert the simulated link obtained from ngrok, then click save ###
