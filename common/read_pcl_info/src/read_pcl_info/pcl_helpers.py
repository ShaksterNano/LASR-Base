#!/usr/bin/env python
import rospy
from sensor_msgs.msg import PointCloud2
from visualization_msgs.msg import Marker
from sensor_msgs.msg import LaserScan
import numpy as np
from std_msgs.msg import Header
from sensor_msgs.msg import LaserScan, PointCloud2
from sensor_msgs import point_cloud2
from geometry_msgs.msg import Point, PointStamped
from math import sqrt, cos, sin
import tf2_ros
import tf2_geometry_msgs

MEAN_DISTANCE_THRESHOLD = 0.5
door_location = Point( x=-5.401556015014648, y= -1.28697669506073)
door_detected = False


def create_point_marker(x, y, z, idx):
    marker_msg = Marker()
    marker_msg.header.frame_id = "xtion_rgb_optical_frame"
    marker_msg.header.stamp = rospy.Time.now()
    marker_msg.id = idx
    marker_msg.type = Marker.SPHERE
    marker_msg.action = Marker.ADD
    marker_msg.pose.position.x = x
    marker_msg.pose.position.y = y
    marker_msg.pose.position.z = z
    marker_msg.pose.orientation.w = 1.0
    marker_msg.scale.x = 0.1
    marker_msg.scale.y = 0.1
    marker_msg.scale.z = 0.1
    marker_msg.color.a = 1.0
    marker_msg.color.r = 0.0
    marker_msg.color.g = 1.0
    marker_msg.color.b = 0.0
    return marker_msg


# get pointcloud
def get_pointcloud():
    pointcloud = rospy.wait_for_message('/xtion/depth_registered/points', PointCloud2)
    return pointcloud


# get the laser scan
def get_laser_scan():
    laser_scan = rospy.wait_for_message('/scan', LaserScan)
    return laser_scan


def filter_laser_scan(laser_scan):
    middle_part = laser_scan.ranges[len(laser_scan.ranges) // 3: 2 * len(laser_scan.ranges) // 3]
    filtered_ranges = [np.nan] * len(laser_scan.ranges)
    filtered_ranges[len(laser_scan.ranges) // 3: 2 * len(laser_scan.ranges) // 3] = middle_part
    mean_distance = np.nanmean(filtered_ranges)
    return mean_distance, filtered_ranges


def limit_laser_scan(laser_scan):
    mean_distance, filtered_ranges = filter_laser_scan(laser_scan)
    limited_scan = laser_scan

    # update the laser scan
    limited_scan.header.stamp = rospy.Time.now()
    limited_scan.ranges = filtered_ranges

    pub.publish(limited_scan)
    rospy.loginfo("published the filtered laser scan")
    rospy.sleep(1)


def get_transform(from_frame, to_frame):
    try:
        t = tf_buffer.lookup_transform(to_frame, from_frame, rospy.Time(0), rospy.Duration(0.5))
        return t
    except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
        raise

def apply_transform(input_xyz, transform, target="xtion_rgb_optical_frame"):
    ps = PointStamped()
    ps.point.x = input_xyz[0]
    ps.point.y = input_xyz[1]
    ps.point.z = input_xyz[2]
    ps.header.frame_id = target
    ps.header.stamp = rospy.Time.now()

    tr_point = tf2_geometry_msgs.do_transform_point(ps, transform)
    return (tr_point.point.x, tr_point.point.y, tr_point.point.z)

def transform_point(point):
    # door_point_map = PointStamped()
    # door_point_map.header.frame_id = "map"  # Assuming the door point is in the "map" frame
    # door_point_map.point.x = -5.401556015014648
    # door_point_map.point.y = -1.28697669506073
    # door_point_map.point.z = 0.0

    tr = get_transform("map", "base_laser_link")
    x, y, z = apply_transform((point[0], point[1], 0.0), tr)
    # return Point(x=x, y=y, z=z)
    return x, y, z

def laser_callback(laser_data):
    global door_detected, door_location
    # Filter the laser scan data based on angle and range
    mean, filtered_points = filter_laser_scan(laser_data)
    print(f"filtered_points: {filtered_points}")

    # filtered_points = []
    # for angle, range_val in zip(laser_data.angle_increment, laser_data.ranges):
    #     if abs(angle) < 0.1 and range_val < 2.0:  # Define angle and range thresholds
    #         filtered_points.append((range_val, angle))

    print(laser_data.header.frame_id)

    final_points = []
    for i, range_val in enumerate(filtered_points):
        # print(f"i: {i}, range_val: {range_val}")
        angle = laser_data.angle_min + i * laser_data.angle_increment
        final_points.append((range_val, angle))

    to_present = []

    for range_val, angle in final_points:
        # if range_val != np.nan:
            # print(f"range_val: {range_val}, angle: {angle}")
        # x = range_val
        # y = range_val
        x = range_val * cos(angle)
        y = range_val * sin(angle)
        to_present.append((x, y))

        dist = sqrt((x - door_location.x) ** 2 + (y - door_location.y) ** 2)
        # else:
        #     dist = np.inf

        print(f"dist: {dist}")
        # print(f"Door detected!{door_detected}")
        if dist < 0.1:  # Adjust the threshold as needed
            door_detected = True
            print(f"Door detected!{door_detected}")
            break

    for i, point in enumerate(to_present):
        if point[0] != np.nan:
            x, y, z = transform_point(point)
            door_pose_laser.publish(create_point_marker(x, y, z, i))

def point_cloud_callback(pcl_data):
    # Filter the point cloud data based on range and height
    filtered_points = []
    for point in point_cloud2.read_points(pcl_data, field_names=("x", "y", "z"), skip_nans=True):
        dist = sqrt((point[0] - door_location.x) ** 2 + (point[1] - door_location.y) ** 2)
        if dist < 0.1 and abs(point[2] - 1.0) < 0.05:  # Adjust the thresholds as needed
            filtered_points.append(point)

    # Check if any points match the expected door location
    if filtered_points:
        door_detected = True


if __name__ == "__main__":
    rospy.init_node("pcl_helpers")
    # publish_laser_topic()
    tf_buffer = tf2_ros.Buffer()
    tf_listener = tf2_ros.TransformListener(tf_buffer)
    pub = rospy.Publisher('/filtered_laser_scan', LaserScan, queue_size=10)
    laser_sub = rospy.Subscriber('/scan', LaserScan, laser_callback)
    # laser_sub = rospy.Subscriber('/scan', LaserScan, limit_laser_scan)
    door_pose_laser = rospy.Publisher("/door_pose_laser", Marker, queue_size=100)
    door_pose = rospy.Publisher("/pose_point", Marker, queue_size=100)
    pcl_sub = rospy.Subscriber('/xtion/depth_registered/points', PointCloud2, point_cloud_callback)
    while not rospy.is_shutdown():
        rospy.spin()
