> Source: https://robomaster-dev.readthedocs.io/en/latest/python_sdk/multi_robot_drone_example.html (DJI, Apache-2.0), converted to Markdown on 2026-11-04.

# 12. Implement Multi-device Formation for TT by Using the RoboMaster SDK

## 12.1. Initialize the drone

Before performing drone-related operations, you must initialize the drone object according to the specified configuration.

- First, import the multi_robot module from the installed multi_robomaster package.:

      from multi_robomaster import multi_robot

- Create a multi_drone instance object of the MultiDrone class. Here, multi_drone\` is a multi-device controller object.:

      multi_drone = multi_robot.MultiDrone()

- Initialize the drone object. Currently, you must specify the number of drones that you want to control to initialize education-series drones.:

      multi_drone.initialize(drone_num)

Now, you have finished initializing the drones.

## 12.2. Number and group drones

To simplify the process of controlling multiple devices, we group them by SN, which is the only unique identifier of a device. Therefore, multi-drone formation is implemented based on SNs. To simplify the formation, the SDK must map custom IDs to drone SNs.

- After initialization, use the instantiated multi_drone object to number SNs.:

      multi_drone.number_id_by_sn([1, "0TQZH79ED00H56"], [2, "0TQZH79ED00H89"])

You can map multiple IDs to the same SN, but only one SN can be mapped to an ID.

- Use the instantiated multi_drone object to group drones.:

      multi_drone_group1 = multi_drone.build_group([1, 2])

The grouping result is multi_drone_group1 for the multi_group object. You can group the same drone multiple times. For example::

    multi_drone_group1 = multi_drone.build_group([1])
    multi_drone_group2 = multi_drone.build_group([1, 2])

- If you do not want to number drones, you can use the number_id_to_all_drone API to implicitly number the drones with random numbers ranging from 0 to drone_num.:

      multi_drone.number_id_to_all_drone()

This completes the grouping of drones. Now, you can perform information query, motion control, and other operations on the drone through relevant interfaces.

## 12.3. Instruct drones to execute commands

- After action grouping, use the instantiated multi_drone object to perform actions.:

      multi_drone.run([multi_drone_group1, base_action_1])

Where, multi_drone_group1 is the grouped multi_group object, and base_action_1 is the user-defined command function, whose format is as follows::

    def base_action_1(robot_group):
        robot_group.get_sn()
        robot_group.get_battery()

If you want multiple groups to perform multiple actions simultaneously, use the following method. Here, we use two groups::

    multi_drone.run([multi_drone_group1, base_action_1],
                    [multi_drone_group2, base_action_2])

You have now had the drones execute commands.

## 12.4. Release drone resources

At the end of the program, you need to manually release the resources related to the drone object, including releasing the network address, ending the corresponding background thread, and releasing the corresponding address space. The multi_drone.close object provides the close() method for releasing these resources, which can be used as follows.:

    multi_drone.close()

Tip

To avoid unexpected errors, be sure to call the close() method at the end of the program.

## 12.5. Use the query interface

The query interface is the data acquisition interface, through which you can obtain the status of the drone and the status of sensors. The following two examples of querying the SN of the drone and querying the battery level of the drone can help you understand the usage of this interface.

### 12.5.1. Example 1: Query the SN and battery level of the drone

- First, complete the operations on the drone object as described in the [\`Control a drone to execute commands\`\_](#id1) section.
- Execute the following code for base_action_1 (base_task in this example):

    def basic_task(robot_group):
        robot_group.get_sn()
        robot_group.get_battery()

The SN and battery level of the drone are printed in the console in the format: “DRONE id: {}, reply: {}”.

- Release relevant resources as described in the [Release drone resources](#release-drone-resources) section.

For the full process, refer to the `/examples/15_multi_robot/multi_drone/02_basic.py` sample file.

    from multi_robomaster import multi_robot


    def basic_task(robot_group):
        robot_group.get_sn()
        robot_group.get_battery()


    if __name__ == '__main__':
        # get drone sn by run the expamles of /15_multi_robot/multi_drone/01_scan_ip.py

        robot_sn_list = ["0TQZH79ED00H56", "0TQZH79ED00H89"]
        sn_list = []
        battery_list = []
        drone_num = 2
        multi_drone = multi_robot.MultiDrone()
        multi_drone.initialize(robot_num=2)
        multi_drone.number_id_by_sn([0, robot_sn_list[0]], [1, robot_sn_list[1]])
        tello_group = multi_drone.build_group([0, 1])
        multi_drone.run([tello_group, basic_task])
        multi_drone.close()

## 12.6. Use the setup interface

The setup interface is used to configure the modules of the drone. This section uses the extended LED module as an example to explain how to use the setup interface.

Tip

Currently, configuring extended LED lights is only supported by Tello Talent devices.

### 12.6.1. Example 1: Configure the extended LED module of the drone

The process of configuring the extended LED module of the drone through the SDK is as follows.

- First, complete the operations on the drone object as described in the [\`Control a drone to execute commands\`\_](#id3) section.
- Execute the following code for base_action_1:

    def base_action_1(robot_group):
        robot_group.set_led(255, 255, 255)
        time.sleep(2)
        robot_group.set_led(command_dict={1: [255, 0, 0], 2: [255, 255, 0]})

Using the set_led(255, 255, 255) interface allows you to light up all drones in the current group white. To set different colors for different drones, use the command_dict keyword. If you use command_dict with the parameter type set to dict, you can set different colors for different drones in the current group. As shown in the previous example, drone 1 lights up red, and drone 2 lights up green.

Note that when you use the command_dict keyword with its parameter type set to dict, other parameters will be ignored. The number of drones in the dictionary must equal the number of drones in the current group rather than the default setting.

- Release relevant resources as described in the [Release drone resources](#release-drone-resources) section.

For the full process, refer to the `/examples/15_multi_robot/multi_drone/06_led.py` sample file.

    import time
    from multi_robomaster import multi_robot


    def base_action_1(robot_group):
        robot_group.set_led(255, 255, 255)
        time.sleep(2)
        robot_group.set_led(command_dict={1: [255, 0, 0], 2: [255, 255, 0]})


    if __name__ == '__main__':
        # get drone sn by run the expamles of /15_multi_robot/multi_drone/01_scan_ip.py

        robot_sn_list = ["0TQZH79ED00H56", "0TQZH79ED00H89"]
        multi_drone = multi_robot.MultiDrone()
        multi_drone.initialize(robot_num=2)
        multi_drone.number_id_by_sn([1, robot_sn_list[0]], [2, robot_sn_list[1]])
        multi_drone_group1 = multi_drone.build_group([1, 2])
        multi_drone.run([multi_drone_group1, base_action_1])
        multi_drone.close()

## 12.7. Use the action interface

The action interface is used to instruct a drone to perform flight actions. This section explains how to use this interface.

Warning

If you use drone firmware v2.5.1.4 and Wi-Fi module v1.0.0.33, you must upgrade the drone before using the action interface, otherwise unexpected flight actions can occur. To locate this information, refer to the interface documentation for standalone devices.

### 12.7.1. Example 1: Control the drone to take off and fly back and forth

In this example, you first need to control two drones to take off and then move them forward and backward 100 cm respectively.

- First, complete the operations on the drone object as described in the [\`Control a drone to execute commands\`\_](#id5) section. Then, write this program:

    from multi_robomaster import multi_robot


    def takeoff_land_task1(robot_group):
        robot_group.takeoff().wait_for_completed()
        robot_group.forward(100).wait_for_completed()
        robot_group.land().wait_for_completed()


    def takeoff_land_task2(robot_group):
        robot_group.takeoff().wait_for_completed()
        robot_group.backward(100).wait_for_completed()
        robot_group.land().wait_for_completed()


    if __name__ == '__main__':
        # get drone sn by run the expamles of /15_multi_robot/multi_drone/01_scan_ip.py

        robot_sn_list = ["0TQZH79ED00H56", "0TQZH79ED00H89"]
        multi_drone = multi_robot.MultiDrone()
        multi_drone.initialize(robot_num=2)
        multi_drone.number_id_by_sn([0, robot_sn_list[0]], [1, robot_sn_list[1]])
        multi_drone_group1 = multi_drone.build_group([0])
        multi_drone_group2 = multi_drone.build_group([1])
        multi_drone.run([multi_drone_group1, takeoff_land_task1],
                        [multi_drone_group2, takeoff_land_task2])
        multi_drone.close()

- Release relevant resources as described in the [Release drone resources](#release-drone-resources) section.

Warning

Different from a standalone drone operation, the wait_for_completed() interface is required when multiple drones perform flight actions. If you forget to include this interface, the next action after the current action may not be performed. With this interface, after waiting for a period of time, the drone performs the next action.

### 12.7.2. Example 2: Control drones to move to the target coordinate point

In this example, you first need to control two drones to take off and then move along a square track at a height of 100 cm and a speed of 100 cm/s. The center of the large carpet is used as the center point and the side length is set to 50 cm.

- First, complete the operations on the drone object as described in the [\`Control a drone to execute commands\`\_](#id7) section.
- Execute the following code for base_action_1:

    def base_action_1(robot_group):
        robot_group.mission_pad_on()
        robot_group.takeoff().wait_for_completed()
        robot_group.go({1: [-50, -50, 100, 100, "m12"], 2: [50, 50, 100, 100, "m12"]}).wait_for_completed()
        robot_group.set_mled_char("r", "heart")
        robot_group.go({1: [-50, 50, 100, 100, "m12"], 2: [50, -50, 100, 100, "m12"]}).wait_for_completed()
        robot_group.set_mled_char("p", "heart")
        robot_group.go({1: [50, 50, 100, 100, "m12"], 2: [-50, -50, 100, 100, "m12"]}).wait_for_completed()
        robot_group.go({1: [50, -50, 100, 100, "m12"], 2: [-50, 50, 100, 100, "m12"]}).wait_for_completed()
        robot_group.land().wait_for_completed()
        robot_group.mission_pad_off()

Note that the go command for multi-device formation forces users to use the mat coordinates for movement. To ensure programming security, the drone’s own coordinate system cannot be used for drone movement. The number of drones in the dictionary must equal the number of drones in the current group rather than the default setting.

- Release relevant resources as described in the [Release drone resources](#release-drone-resources) section.

For the full process, refer to the `/examples/15_multi_robot/multi_drone/05_go.py` sample file.

    from multi_robomaster import multi_robot


    def base_action_1(robot_group):
        robot_group.mission_pad_on()
        robot_group.takeoff().wait_for_completed()
        robot_group.go({1: [-50, -50, 100, 100, "m12"], 2: [50, 50, 100, 100, "m12"]}).wait_for_completed()
        robot_group.set_mled_char("r", "heart")
        robot_group.go({1: [-50, 50, 100, 100, "m12"], 2: [50, -50, 100, 100, "m12"]}).wait_for_completed()
        robot_group.set_mled_char("p", "heart")
        robot_group.go({1: [50, 50, 100, 100, "m12"], 2: [-50, -50, 100, 100, "m12"]}).wait_for_completed()
        robot_group.go({1: [50, -50, 100, 100, "m12"], 2: [-50, 50, 100, 100, "m12"]}).wait_for_completed()
        robot_group.land().wait_for_completed()
        robot_group.mission_pad_off()


    if __name__ == '__main__':
        # get drone sn by run the expamles of /15_multi_robot/multi_drone/01_scan_ip.py

        robot_sn_list = ["0TQZH79ED00H56", "0TQZH79ED00H89"]
        multi_drone = multi_robot.MultiDrone()
        multi_drone.initialize(robot_num=2)
        multi_drone.number_id_by_sn([1, robot_sn_list[0]], [2, robot_sn_list[1]])
        multi_drone_group1 = multi_drone.build_group([1, 2])
        multi_drone.run([multi_drone_group1, base_action_1])
        multi_drone.close()
