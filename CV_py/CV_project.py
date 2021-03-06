import cv2
import numpy as np
import math

WIDETH = 1280
HEIGHT = 720
error_alpha = 0.5
radius_alpha = 0.5
max_radius = 120
min_radius = 5
cnt_threshold = 10

# method_num = 0  # 定位方法选择

camera_matrix = np.array(([693.2, 0, 666.8], # 内参矩阵
                          [0, 693.4, 347.7],
                          [0, 0, 1]), dtype=np.double)
dist_coefs = np.array([-0.050791, 0.217163, 0.0000878, -0.000388, -0.246122],
                      dtype=np.double) # k1 k2 p1 p2 k3
object_3D_points = np.array(([-60, 148.32 ,0 ], [-25, 116.03, 0], [25, 116.03, 0], [60, 148.32, 0],
                             [-25, 158.03, 0], [25, 158.03, 0], [-25, 200.03, 0], [25, 200.03, 0]),
                            dtype=np.double)    # 世界坐标系上的坐标
#  目标坐标构建如下：
# ---2-----3---->X
#       |
#  1    |    4
#    5  |  6
#       |
#    7  |  8
#       |
#       V
#       Y

class Point:
    def __init__(self, x_param, y_param, num):
        self.x = x_param
        self.y = y_param
        self.n = num

#------筛选椭圆函数，待修正------#
def checkEllipse_simple(img, cen_x, cen_y, a_double, b_double, theta): # 函数功能：初步识别检测出靶标的椭圆（不稳定）
    x, y = int(np.around(cen_x)), int(np.around(cen_y)) # 近似化，img像素数组只考虑整数位置
    a, b = int(np.around(a_double / 2)), int(np.around(b_double / 2))
    theta = theta * math.pi/180.0   # 角度转弧度
    # 越界pass
    if x + a+3 > WIDETH or y + a+3 > HEIGHT:
        return False
    if x - a <0 or y - a <0:
        return False
    # 框内有黑pass
    for i in range(0, b-1):
        if img[y, x + i] == 0 or img[y, x - i] == 0:
            return False
        if img[y - i, x] == 0 or img[y + i, x] == 0:
            return False
    # 边界的短轴外一点儿有白色pass
    for m in range(b+1, b+2):
        offset_x = m * math.cos(theta)
        offset_y = m * math.sin(theta)
        if theta > 90:
            offset_x *= -1.0

        x_r = int(np.around(cen_x + offset_x))
        y_r = int(np.around(cen_y + offset_y))
        x_l = int(np.around(cen_x - offset_x))
        y_l = int(np.around(cen_y - offset_y))

        if img[y_r, x_r] == 255 or img[y_l, x_l] == 255:
            #cv2.circle(img, (x_l, y_l), 2, (255, 0, 0), -1)
            return False
    return True

# -------对符合的椭圆重排序-------#
def locatePoint(p_list, lp_list, radius): # 函数功能：稳定完整的实现靶标定位
    temp = []
    for i in range(0, len(p_list)):  # 复制p_list给temp,为了保留p_list
        addPoint(p_list, temp, i, i+1)
    #                   3 6
    #   标准位置定义:   7     8
    #                   2 5
    #                   1 4
    #-----筛选出中间6点位置-----#
    Error = radius * error_alpha  # 用距离圆心占半径的百分比评估误差
    num = 0
    for i in range(0, len(p_list)):
        for j in range(i+1, len(p_list)):
            med_x = (p_list[i].x + p_list[j].x) / 2
            med_y = (p_list[i].y + p_list[j].y) / 2

            for m in range(0, len(p_list)):
                if m == i or m == j: continue
                # 用距离和半径的百分比做误差评估
                error = math.sqrt((med_x - p_list[m].x) ** 2 + (med_y - p_list[m].y) ** 2)
                if error < Error:
                    addPoint(p_list, lp_list, i, num+1)     #  1  4
                    addPoint(p_list, lp_list, m, num+2)     #  2  5
                    addPoint(p_list, lp_list, j, num+3)     #  3  6
                    num += 3
                    # 以上一定要找出需要的6点，否则算作无法进行进一步的计算。
                    temp[i].n = -1  # -1说明已经选定
                    temp[m].n = -1
                    temp[j].n = -1

    #-----确定7\8点------#
    if len(lp_list) == 6:
        for p in range(0, len(p_list)):
            if temp[p].n == -1:
                continue
            if distance(p_list, lp_list, p, 1) > 5*radius and distance(p_list, lp_list, p, 4) > 5*radius:
                continue# 根据距离进一步筛选
            else:
                num += 1
                addPoint(p_list, lp_list, p, num)   # 7 和 8 添加进数组
        # 至此，lpoint_list已经实现了对p_list中元素的简单排序

def choosePoints_method1(lp_list, cp_list):
    if len(lp_list) < 8:
        pass
    else:
        cen_78_y = (lp_list[6].y + lp_list[7].y) / 2  # 7 和 8 两点的中点的纵坐标
        cen_25_y = (lp_list[1].y + lp_list[4].y) / 2  # 2 和 5 两点的中点的纵坐标
        if cen_78_y < cen_25_y:
            position = True # 图像为正
        else:
            position = False # 图像为负
        #-------最直接的定位方案实现--------#
        #                   2 3
        #   最终位置定义:   1     4
        #                   5 6
        #                   7 8
        if position == True:
            if lp_list[6].x > lp_list[7].x:
                swapPoint(lp_list, 6, 7)    # 7\8点交换
            if lp_list[2].x > lp_list[5].x:
                swapPoint(lp_list, 2, 5)    # 3\6点交换
            if lp_list[1].x > lp_list[4].x:
                swapPoint(lp_list, 1, 4)    # 2\5点交换
            if lp_list[0].x > lp_list[3].x:
                swapPoint(lp_list, 0, 3)    # 1\4点交换

            addPoint(lp_list, cp_list, 6, 1)
            addPoint(lp_list, cp_list, 2, 2)
            addPoint(lp_list, cp_list, 5, 3)
            addPoint(lp_list, cp_list, 7, 4)
            addPoint(lp_list, cp_list, 1, 5)
            addPoint(lp_list, cp_list, 4, 6)
            addPoint(lp_list, cp_list, 0, 7)
            addPoint(lp_list, cp_list, 3, 8)
        else:
            if lp_list[6].x < lp_list[7].x:
                swapPoint(lp_list, 6, 7)    # 7\8点交换
            if lp_list[0].x < lp_list[3].x:
                swapPoint(lp_list, 0, 3)    # 1\4点交换
            if lp_list[1].x < lp_list[4].x:
                swapPoint(lp_list, 1, 4)    # 2\5点交换
            if lp_list[2].x < lp_list[5].x:
                swapPoint(lp_list, 2, 5)    # 1\4点交换

            addPoint(lp_list, cp_list, 6, 1)
            addPoint(lp_list, cp_list, 0, 2)
            addPoint(lp_list, cp_list, 3, 3)
            addPoint(lp_list, cp_list, 7, 4)
            addPoint(lp_list, cp_list, 1, 5)
            addPoint(lp_list, cp_list, 4, 6)
            addPoint(lp_list, cp_list, 2, 7)
            addPoint(lp_list, cp_list, 5, 8)

def choosePoints_method2(lp_list, cp_list): # 用HU不变距做计算,没想好怎么实现。
    pass

def distance(list_1, list_2, i, j): # 计算list_1第i个索引点和list_2第j个索引点的距离
    return math.sqrt((list_1[i].x - list_2[j].x) ** 2 + (list_1[i].y - list_2[j].y) ** 2)

def swapPoint(list, i, j): # 交换list中第i个索引和第j个索引数据的位置、索引
    list[i].n, list[j].n = j+1, i+1
    list[i], list[j] = list[j], list[i]

def addPoint(src_list, new_list, i, n): #将src_list中的第i个索引的数据添加进new_list，且num为n
    new_list.append(Point(src_list[i].x, src_list[i].y, n))

def main():
    cap = cv2.VideoCapture(1)
    if (cap.isOpened() == False):
        print("Failed to open the camera...")
    else:
        ret = cap.set(3, WIDETH) # 设置显示尺寸 1280*720
        ret = cap.set(4, HEIGHT)
        font = cv2.FONT_HERSHEY_SIMPLEX  # 字体设置
        # demo录制
        # fourcc = cv2.VideoWriter_fourcc(*'XVID')
        # out = cv2.VideoWriter('output.avi', fourcc, 20.0, (1280, 720))
        while(True):
            ret, img = cap.read()
            ret, frame = cap.read()
            
            # 每次循环初始化列表
            point_list = []
            lpoint_list = []
            choose_point_list = []
            image_2D_points = []
            num_list = []

            #-----一帧基础图形处理-----#
            f_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            f_bulr = cv2.GaussianBlur(f_gray, (5, 5), 0)
            # equ = cv2.equalizeHist(f_gray)
            # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            # cl1 = clahe.apply(f_gray)
            # ret, f = cv2.threshold(f_gray, 127, 255, cv2.THRESH_BINARY_INV)
            # ret, f_thresh_equ = cv2.threshold(cl1, 127, 255, cv2.THRESH_BINARY_INV)  # 阈值127，变成255

            ret, f_thresh = cv2.threshold(f_gray, 127, 255, cv2.THRESH_BINARY_INV)
            f_can = cv2.Canny(f_gray, 300, 400, 3)

            #-----一帧椭圆检测-------#
            image, contours, hierarchy = cv2.findContours(f_can, cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            count = 0 # 用来计数
            sum = 0  # 用来统计半径

            for cnt in contours:
                if len(cnt) > cnt_threshold: # 点数超过10才能拟合椭圆，算法中要求是6点
                    ell = cv2.fitEllipse(cnt)

                    # ell的数据内容,是对椭圆的最小矩阵拟合
                    b_double, a_double = ell[1][0], ell[1][1]   # 拟合的矩阵宽\长
                    cen_x, cen_y = ell[0][0], ell[0][1]   # 矩阵中心坐标
                    theta = ell[2]  # 旋转角度

                    #-----椭圆尺寸基本筛选-----#
                    if a_double > max_radius or b_double > max_radius:  continue
                    if a_double < min_radius or b_double < min_radius:  continue
                    if a_double < b_double * radius_alpha or b_double < a_double * radius_alpha:  continue

                    #-----椭圆进一步筛选------#
                    if  checkEllipse_simple(f_thresh, cen_x, cen_y, a_double, b_double, theta):
                        count += 1
                        sum += b_double/2   # sum是所有短半轴的集合
                        point_list.append(Point(cen_x, cen_y, count))

                        #------画椭圆及圆心-----#
                        cv2.ellipse(frame, ell, (0, 0, 255), 2)
                        cv2.circle(frame, (int(cen_x), int(cen_y)), 2, (0, 0, 255), -1)
                        num_list.append(len(cnt))
            #----一帧椭圆检测结束-----#

            #-----处理圆心坐标点集-----#
            if len(point_list) < 8:
                cv2.putText(img, 'No enough ellipse in sight!', (50, 50), font, 1, (0, 0, 255), 2, cv2.LINE_AA)
            else:
                #-----重定位和排序------#
                locatePoint(point_list, lpoint_list, sum/count) # 8点排序定位
                choosePoints_method1(lpoint_list, choose_point_list)    # 确定计算的点

                if len(choose_point_list) == 8:
                    for i in range(0, len(choose_point_list)):
                        cv2.putText(img, str(choose_point_list[i].n), (int(choose_point_list[i].x), int(choose_point_list[i].y)), font, 1, (0, 255, ), 2,
                                    cv2.LINE_AA)
                    for i in range(0, len(point_list)):
                        cv2.putText(frame, str(point_list[i].n), (int(point_list[i].x), int(point_list[i].y)), font, 1, (0, 255, 0), 2,
                                    cv2.LINE_AA)

                    #-------位姿解算solvePNP-------#
                    for i in range(0, len(choose_point_list)):
                        image_2D_points.append((choose_point_list[i].x, choose_point_list[i].y))
                    image_2D_points = np.array(image_2D_points, dtype=np.double) # list转array
                    found, rvec, tvec = cv2.solvePnP(object_3D_points, image_2D_points, camera_matrix, dist_coefs)
                    
                    #-------测试matchShape()------#
                    object_3D_test = np.array(([-60, 148.32], [-25, 116.03], [25, 116.03], [60, 148.32],
                                                 [-25, 158.03], [25, 158.03], [-25, 200.03], [25, 200.03]), dtype=np.double)
                    retval_1 = cv2.matchShapes(object_3D_test, image_2D_points, cv2.CONTOURS_MATCH_I1, 0)
                    cv2.putText(img, "HU_method1:" + str(retval_1), (50, 400), font, 1, (0, 0, 255), 2, cv2.LINE_AA)
                    # -----计算欧拉角----#
                    rotM = cv2.Rodrigues(rvec)[0]  # 旋转向量转换成旋转矩阵
                    theta_Z = math.atan2(rotM[1, 0], rotM[0, 0]) * 180.0 / math.pi
                    theta_Y = math.atan2(-1.0 * rotM[2, 0], math.sqrt(rotM[2, 1] ** 2 + rotM[2, 2] ** 2)) * 180.0 / math.pi
                    theta_X = math.atan2(rotM[2, 1], rotM[2, 2]) * 180.0 / math.pi
                    # 相机坐标系下值
                    x, y, z = tvec[0], tvec[1], tvec[2]
                    cv2.putText(img, "X_axis:" + str(x), (50, 100), font, 1, (255, 0, 0), 2, cv2.LINE_AA)
                    cv2.putText(img, "Y_axis:" + str(y), (50, 150), font, 1, (255, 0, 0), 2, cv2.LINE_AA)
                    cv2.putText(img, "Z_axis:" + str(z), (50, 200), font, 1, (255, 0, 0), 2, cv2.LINE_AA)
                    cv2.putText(img, "X_theta:" + str(theta_X), (50, 250), font, 1, (0, 255, 0), 2, cv2.LINE_AA)
                    cv2.putText(img, "Y_theta:" + str(theta_Y), (50, 300), font, 1, (0, 255, 0), 2, cv2.LINE_AA)
                    cv2.putText(img, "Z_theta:" + str(theta_Z), (50, 350), font, 1, (0, 255, 0), 2, cv2.LINE_AA)
                    
                    # 对第五个点进行验证，此处选取靶标中最上面2点的中点作为验证点
                    extrinsics_matrix = np.concatenate((rotM, tvec), axis=1) # 矩阵拼接，旋转矩阵R和平移矩阵t组成齐次矩阵
                    projection_matrix = np.dot(camera_matrix, extrinsics_matrix)     # np.dot(a,b):a*b矩阵相乘
                    # 计算世界坐标原点在相机图像中的新坐标
                    pixel = np.dot(projection_matrix, np.array([0, 0, 0, 1], dtype=np.double))
                    pixel_unit = pixel / pixel[2]   # 归一化
                    cv2.circle(img, (int(np.around(pixel_unit[0])), int(np.around(pixel_unit[1]))), 3, (0, 0, 255), -1)
            
            cv2.imshow('choose_point_list', img)
            cv2.imshow('point_list', frame)

            k = cv2.waitKey(1) & 0xff
            if k == 27:
                break
            # if k == 32:
            #     cv2.imwrite("D:/save/"+str(s_num)+".png", img)
            #     s_num += 1
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()

