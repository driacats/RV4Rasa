# A Monitor for Rasa

**RV4Rasa** is a Runtime Verification Monitor developed for Rasa.

## Roadmap 
 - [x] Send slots in the message

 - [x] Use websocket instead of socket

 - [x] Send answer action to monitor

 - [ ] Create two custom actions for error messages on different code error from monitor one for user and one for bot

 - [ ] Example on factory scenario

   It needs three different errors: protocol violation by user or by bot, standard errors (check confidence, guarantee reliability)

   - [ ] Create factory scenario on Godot
   - [ ] Create factory chatbot
   - [ ] Connect them using VEsNA
   - [ ] Create and connect the monitor

## Installation

### Install from scratch the example

First of all we have to create a virtual environment that uses python 3.9

```bash
python3.9 -m venv ./venv
source ./venv/bin/activate
```

Then you can install the needed dependencies using the `requirements.txt` file as follows:

```bash
pip install -r requirements.txt
```

Clone this repository in the same folder. You can:

1. Train the model using `rasa train`
2. Use the last trained model and try the chat using `rasa shell` 

To see RV4Rasa in action launch the shell and the `websocket-server` using

```
python websocket-server.py
```

The websocket for the moment does a stupid check whether the user input contains or not the word `bot`.

### Install on working chatbot

If you have already a working chatbot and you want to add a runtime verification you have to follow these steps:

1. Create a folder called `policies` inside your chatbot;
2. Clone the `ControllerPolicy.py` file inside the `policies` folder;
3. If you have not installed it already, install `websocket-client` and `regex` python packages;
4. Add the policy to the policies in the `config.yml` file with highest priority.

## Guide

I will now try to give a short idea of what is happening so that you can customize it. Let me start from the beginning, since RV4Rasa uses a custom policy called **ControllerPolicy** you have to include it in the policies used by the chatbot in the `config.yml` file as follows:

```yaml
  - name: policies.controllerPolicy.ControllerPolicy
    priority: 6
    error_action: "utter_error_message"
```

Note three important things:

- The `ControllerPolicy` wants the higher priority in the policies list;
- `error_action` is the action that will be performed when an error is encountered. Giving that is an action it could also be a custom action, obviously;
- The `ControllerPolicy` class is inside a `policies` folder.

Remember to create the `error-action` and declare it in the `domain.yml` file. In the example case:

```yaml
responses:

  ...

  utter_error_message:
  - text: "You cannot say `bot` inside a sentence!"
```

You can change it to whatever you want and customize it also to be more and more complex using all the rasa features.

The `ControllerPolicy`  sends:

- one message that contains the data of the user input;
- one message that contains the data of the action chosen by the chatbot.

The message is sent using **websocket** on the 5002 port and waits for a string answer that can be either **True** if the message is accepted or **False** if not.

## Changelog (Italian)

### 13.04.2023

- Creato repo github;
- La policy è funzionante e manda:
	- il testo del messaggio ricevuto
	- l'intent riconosciuto
	- le entities riconosciute
	- la lista degli events avvenuti
	- gli slots
	- il nome dell'ultima azione eseguita
- Sia il monitor sia la policy usano ora websocket

> _Nota: la policy usa il pacchetto `websocket-client` anziché `websockets`. Questo perché la policy viene fatta girare su un thread asincrono con asyncio: non è possibile lanciare un thread async (richiesto da websockets) da uno che lo sia già. Una possibile soluzione è usando `nest-asyncio` ma bisognerebbe andarlo ad inserire nella classe principale di Rasa, modificando a quel punto l'intero programma e rendendolo non portabile._

### 14.04.2023

- Risolti alcuni problemi nelle stringhe regex (rese raw strings e aggiunto notazione specifica per i null che non sono tra virgolette)
- Pulizia del codice: rimozione di alcune stampe e controlli inutili, funzione `create` mai chiamata, la riporto qui sotto nel caso fosse necessario reinserirla.

```python
@classmethod
def create(cls, config: Dict[Text, Any], model_storage: ModelStorage, resource: Resource, execution_context: ExecutionContext, **kwargs:An    y):
	return cls(config, model_storage, resource, execution_context)  
```

- La next action viene ora mandata al monitor anche se in un tempo diverso rispetto al resto.

  > *Nota: rasa lancia un tracker per ogni possibile story che stiamo seguendo più uno sempre pronto sulla listen. Quello sulla listen permette di eseguire la policy una sola volta per ogni messaggio, ma sono gli altri a contenere i valori delle azioni da eseguire. Ad esempio nel template di prova, se scrivo "Hello" vengono generati due tracker, uno con azione "utter_greet"  e uno con azione "action_listen".*
  >
  > *In questo momento ho deciso di lasciare le next actions ad un invio successivo al server sempre formattate in json perché altrimenti su chatbot complessi si moltiplicherebbe il numero di messaggi in arrivo al server. Le soluzioni sono due: o il monitor è in grado di gestire tale situazione o bisogna pensare ad un passagio intermedio.*

- Aggiunti `sender` e `receiver` nei json mandati.
