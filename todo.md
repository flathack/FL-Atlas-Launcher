# FL Atlas Launcher

## TODO
- Wenn die EXE als Prozess läuft, soll das Icon leuchten. 
- Mit Rechtsklick auf das Icon eines Freelancer, kann man die EXE Datei dann stoppen (z. B. Freelancer.exe). 
- Cheater Mode: Wenn dieser Aktiv ist, kann man das spiel verändern. 
- BINI Konvertierung bei ausgewählter Freelancer Installation
- Wenn Cheater Mode aktiv ist, erscheint eine Sidebar auf der rechten Seite. Hier werden alle verfügbaren Mods angezeigt.
- Folgende Mods sollen erstellt werden:
1. Cruise Charge Time ändern: steht in DATA\constants.ini
2. Reveal Everything: das skript: set_jump_object_visit.py. Zusätzlich noch ändern: bei universe.ini alle visit = 128 durch visit = 1 ersetzen.
3. Ship Handling: SHIPS\shiparch.ini
da gibt es bei den Schiffeinträgen folgendes:
steering_torque = 24000.000000, 24000.000000, 58000.000000
angular_drag = 15000.000000, 15000.000000, 35000.000000
rotation_inertia = 2800.000000, 2800.000000, 1000.000000
bei dem Shiphandling Mod werden alle Schiffe aufgezählt in einer Tabelle (ein Extra Fenster wäre gut, weil das sind viele Schiffe.). Dann kann man eine "Ziel" Händling pro Schiff angeben, z. b. rh_freighter -> li_fighter. DAnn werden die werde von li_fighter nach rh_freighter kopiert. Es soll dann auch gespeichert werden, was verändert wurde, damit man dies wieder rückgängig machen kann und den ursprungszustand zurücksetzen kann.


einen weiteren bonus: wenn der cheat mode aktiv ist, will ich einen NPC in jeder basis haben. Der Name des NPCs soll "Steven" sein und ein weiterer NPC Namens "Helfried". Er soll genau so aussehen wie Edison Trent (der spieler charakter). Der NPC soll einen rumor erzählen. dieser rumor soll folgendes beinhalten: Beste Traderoute von dieser Base zum nächsten base, max 1 sprung entfernt. Er soll dann erzählen was man kaufen muss und wo man es verkaufne muss (System -> Basename). Ist das möglich? 
