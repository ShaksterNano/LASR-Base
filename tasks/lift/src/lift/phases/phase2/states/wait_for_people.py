#!/usr/bin/env python3
import smach, os, rospy
from sensor_msgs.msg import Image
from tiago_controllers.helpers.pose_helpers import get_pose_from_param
from interaction_module.srv import AudioAndTextInteraction, AudioAndTextInteractionRequest, \
    AudioAndTextInteractionResponse

class WaitForPeople(smach.State):
    def __init__(self, controllers, voice, yolo, speech):
        smach.State.__init__(self, outcomes=['success', 'failed'])

        self.controllers = controllers
        self.voice = voice
        self.yolo = yolo
        self.speech = speech

    def execute(self, userdata):
        # wait and ask
        self.voice.speak("How many people are thinking to go in the lift?")
        self.voice.speak("Please answer with a number.")

        req = AudioAndTextInteractionRequest()
        req.action = "ROOM_REQUEST"
        req.subaction = "ask_location"
        req.query_text = "SOUND:PLAYING:PLEASE"
        resp = self.speech(req)

        print("The response of asking the people is {}".format(resp.result))

        # get the answer
        count = 0
        # count = resp.result

        state = self.controllers.base_controller.ensure_sync_to_pose(get_pose_from_param('/wait_centre/pose'))
        rospy.loginfo("State of the robot in wait for people is {}".format(state))
        rospy.sleep(0.5)

        # send request - image, dataset, confidence, nms
        image = rospy.wait_for_message('/xtion/rgb/image_raw', Image)
        detections = self.yolo(image, "yolov8n.pt", 0.3, 0.3)

        # segment them as well and count them
        count_people = 0
        count_people = sum(1 for det in detections.detected_objects if det.name == "person")

        self.voice.speak("I see {} people".format(count_people))

        if count_people < count:
            return 'failed'
        else:
            return 'success'


        # check if they are static with the frames
