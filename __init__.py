# -*- coding: utf-8 -*-
# notify types are info, success, warning or danger
import time

from modules.core.props import Property, StepProperty
from modules.core.step import StepBase
from modules import cbpi

@cbpi.step
class Message_CG(StepBase):

    messagetodisplay = Property.Text("Message To Display", configurable=True, default_value="Message you want to display", description="Message to be displayed")
    timer = Property.Number("Seconds to wait for next step (use 0 to wait for user)?", configurable=True, default_value=1, description="How long should the brew session wait before continuing? If you select 0 then it will wait for user to click Start Next Step.")
    s = False

    @cbpi.action("Start Timer")
    def start(self):
        self.s = False
        if self.is_timer_finished() is None:
            self.start_timer(int(self.timer)+1)

    def reset(self):
        self.stop_timer()

    def execute(self):
        if self.is_timer_finished() is None:
            self.start_timer(int(self.timer)+1)
        if self.s == False:
            self.s = True
            if int(self.timer) == 0:
                self.notify(self.messagetodisplay, "Please select \"Next Step\" to continue", type="warning", timeout=None)
            else:
                self.notify(self.messagetodisplay, "Brewing will continue automatically when the timer completes.", type="info", timeout=((int(self.timer)-1)*1000))
        if self.is_timer_finished() == True:
            if int(self.timer) == 0:
                pass
            else:
                self.next()

@cbpi.step
class CFCWhirlpool_CG(StepBase):

    kettle = StepProperty.Kettle("Kettle", description="Kettle in which the chilling takes place")
    chiller = StepProperty.Actor("Chiller", description="Actor that controls the Chiller")
    chillerPump = StepProperty.Actor("chillerPump", description="Actor that controls the chillerPump")
    temp = Property.Number("Whirlpool Temperature", configurable=True, default_value=68, description="Target Temperature of Whirlpool")
    timer = Property.Number("Total Whirlpool Timer in Minutes (incl. Santise Time)", configurable=True, default_value=30, description="Timer is started immediately")
    sanitiseTimer = Property.Number("Sanitise Timer in Minutes", configurable=True, default_value=5, description="Time at sanitisation temp")
    sanitiseTemp = Property.Number("Sanitise Temperature", configurable=True, default_value=95, description="Target Temperature for sanitisation")
    s_end = 1
    stage = "init" #This process goes through the following stages: init, waithookup, sanitise, whirlpool
    c_cut = 0
    
    def init(self):
        self.stage = "init"
        self.actor_off(int(self.chillerPump))
        self.actor_off(int(self.chiller))
        self.set_target_temp(self.sanitiseTemp, self.kettle)
        self.s_end = 1
        self.c_cut = 0
    
    def start(self):
        pass

    def reset(self):
        self.stop_timer()

    def finish(self):
        self.actor_off(int(self.chillerPump))
        self.actor_off(int(self.chiller))
    
    @cbpi.action("Chiller Connected")
    def chiller_connected(self):
        if self.stage == "waithookup":
            self.stage = "sanitise"
            self.actor_on(int(self.chillerPump))
            self.s_end = (self.timer_remaining() - (60 * int(self.sanitiseTimer)))
        else:
            self.notify("No Action Taken", "Function only works in \"waithookup\" sub-stage. Current stage: " + self.stage, type="info", timeout=5000)
    
    def execute(self):
        if self.is_timer_finished() is None:
            self.start_timer(int(self.timer) * 60)
        if self.is_timer_finished() == True:
            if self.stage != "whirlpool":
                self.notify("ERROR - Whirlpool incomplete", "Step completed without reaching internal whirlpool stage", type="danger", timeout=None)
            self.actor_off(int(self.chiller))
            self.actor_off(int(self.chillerPump))
            self.next()
        else:
            if self.get_kettle_temp(self.kettle) >= (self.get_target_temp(self.kettle)+10): #This option determines when the chiller is full on
                self.actor_on(int(self.chiller))
            elif self.get_kettle_temp(self.kettle) >= self.get_target_temp(self.kettle): #This option specifies partial activation - alternate 3secs on and off
                self.c_cut = int((self.timer_remaining()/3))
                if self.c_cut%2:
                    self.actor_on(int(self.chiller))
                else:
                    self.actor_off(int(self.chiller))
            else:
                self.actor_off(int(self.chiller))
        if self.stage == "init":
            self.notify("Put on the lid and connect the chiller", "Please select \"Chiller Connected\" to continue", type="warning", timeout=None)
            self.stage = "waithookup"
        elif self.stage == "sanitise":
            if self.s_end >= self.timer_remaining():
                self.stage = "whirlpool"
                self.set_target_temp(self.temp, self.kettle)

@cbpi.step
class Chill_CG(StepBase):

    kettle = StepProperty.Kettle("Kettle", description="Kettle in which the chilling takes place")
    chiller = StepProperty.Actor("Chiller", description="Actor that controls the Chiller")
    chillerPump = StepProperty.Actor("chillerPump", description="Actor that controls the chillerPump")
    chillerTemp = StepProperty.Sensor("Chiller Temp", description="Sensor that shows the chiller temperature")
    cutoutvariance = Property.Number("Variance between kettle and chiller for end", configurable=True, default_value=0.3, description="The step will end when the kettle temp falls to within this much of the chiller temp.")
    
    def init(self):
        self.actor_on(int(self.chillerPump))
        self.actor_on(int(self.chiller))
        self.set_target_temp(0, self.kettle)
    
    def start(self):
        pass

    def reset(self):
        pass

    def finish(self):
        self.actor_off(int(self.chillerPump))
        self.actor_off(int(self.chiller))
    
    def execute(self):
        if self.get_kettle_temp(self.kettle) <= (self.get_sensor_value(self.chillerTemp)+float(self.cutoutvariance)):
            self.notify("Chill Stage Complete", "Kettle reached: " + str(self.get_kettle_temp(self.kettle)), type="success", timeout=None)
            self.actor_off(int(self.chiller))
            self.actor_off(int(self.chillerPump))
            self.next()


@cbpi.step
class MashOutPreBoil_CG(StepBase):

    kettle = StepProperty.Kettle("Kettle", description="Kettle in which the chilling takes place")
    temp = Property.Number("MashOut Temperature", configurable=True, default_value=76.7, description="Target Temperature of Mashout")
    timer = Property.Number("MashOut Timer in Minutes", configurable=True, default_value=10, description="Time to be held at Mashout temp")
    stage = "init" #This process goes through the following stages: init, mashout, sparge, preboil, hotbreak
    preboiltemp = 90
    hotbreaktemp = 99
    wait_user = False

    def init(self):
        self.stage = "init"
        self.wait_user = False
        self.set_target_temp(self.temp, self.kettle)
        # self.preboiltemp = self.api.cache.get("kettle").get(self.kettle).get_config_parameter("e_max_temp_pid")
        # self.hotbreaktemp = 99
    
    def start(self):
        pass

    def reset(self):
        pass

    def finish(self):
        pass
    
    @cbpi.action("Sparge Complete")
    def sparge_complete(self):
        if self.stage == "sparge":
            self.stage = "preboil"
            self.wait_user = False
            self.set_target_temp(self.preboiltemp, self.kettle)
        else:
            self.notify("No Action Taken", "Function only works in \"sparge\" sub-stage. Current stage: " + self.stage, type="info", timeout=5000)

    @cbpi.action("Removed Lid")
    def lid_removed(self):
        if self.stage == "preboil":
            self.stage = "hotbreak"
            self.wait_user = False
            self.set_target_temp(self.hotbreaktemp, self.kettle)
        else:
            self.notify("No Action Taken", "Function only works in \"preboil\" sub-stage. Current stage: " + self.stage, type="info", timeout=5000)

    @cbpi.action("Hotbreak Finished")
    def hotbreak_finished(self):
        if self.stage == "hotbreak":
            self.wait_user = False
            self.next()
        else:
            self.notify("No Action Taken", "Function only works in \"hotbreak\" sub-stage. Current stage: " + self.stage, type="info", timeout=5000)

    def execute(self):
        if self.stage == "init": #let the kettle heat to mash out temp
            if self.get_kettle_temp(self.kettle) >= self.temp:
                self.stage = "mashout"
        elif self.stage == "mashout": #run the mash timer
            if self.is_timer_finished() is None:
                self.start_timer(int(self.timer) * 60) 
            if self.is_timer_finished() == True:
                self.stage = "sparge"
        elif self.stage == "sparge": #wait for user confirmation to continue
            if self.wait_user == False:
                self.notify("MASH OUT COMPLETE", "Sparge and then select \"Sparge Complete\" to continue.", type="warning", timeout=None)
                self.wait_user = True
        elif self.stage == "preboil": #let the kettle heat to pre-boil, then wait for user to remove lid
            if self.get_kettle_temp(self.kettle) >= self.preboiltemp:
                if self.wait_user == False:
                    self.notify("REMOVE THE LID", "Heated to Pre-Boil. Remove the lid and click \"Removed Lid\" to continue.", type="warning", timeout=None)
                    self.wait_user = True
        elif self.stage == "hotbreak": #heat kettle to boil, then wait for user for user to go to boil stage
            if self.get_kettle_temp(self.kettle) >= self.hotbreaktemp:
                if self.wait_user == False:
                    self.notify("WATCH FOR HOTBREAK", "When hotbreak is complete click \"Hotbreak Finished\" to continue.", type="warning", timeout=None)
                    self.wait_user = True
        else: #An error has occured! Not in a valid status
            self.notify("INVALID STAGE", "An invalid stage has been returned. Current stage: " + self.stage, type="dangar", timeout=None)

            