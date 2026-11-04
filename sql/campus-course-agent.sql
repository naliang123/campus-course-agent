-- 校园课程智能助手 · 完整初始化脚本
-- 包含：users / courses / schedules / study_plans / kb_documents 及演示数据
-- 注意：脚本含 DROP TABLE，重复执行会清空业务数据，请勿在正式库上误跑。
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `kb_documents`;
DROP TABLE IF EXISTS `study_plans`;
DROP TABLE IF EXISTS `schedules`;
DROP TABLE IF EXISTS `courses`;
DROP TABLE IF EXISTS `users`;

-- ----------------------------
-- 用户表（脚手架原有）
-- ----------------------------
CREATE TABLE `users`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '账号',
  `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码',
  `name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '名称',
  `role` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '角色：student-学生，admin-管理员',
  `email` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '邮箱',
  `phone` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '手机号',
  `avatar` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '头像',
  `status` int NOT NULL DEFAULT 1 COMMENT '状态：0-禁用，1-正常',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `username`(`username` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '用户信息表';

INSERT INTO `users` VALUES (1, 'admin', '$2b$12$ypJClLKejFCsyn2eltOco.YAmXory0HFjh7E/oHu9MBzDZZ6wYSSi', '管理员', 'admin', 'admin@system.cn', '13988776699', '/uploads/1790046856623_dc4830aa.jpg', 1, '2026-09-11 15:30:07', '2026-09-22 11:14:34');
INSERT INTO `users` VALUES (2, 'aaa', '$2a$10$phJ2k4sP5.c7T/LuXwzyTu/AlbbOFXblsAZEW6mIfh3koVxQ3Hhny', '小白', 'student', 'xiaobai@qq.com', '13899776688', '/uploads/1790046891012_452a9884.png', 1, '2026-09-09 16:56:41', '2026-09-22 11:14:52');
INSERT INTO `users` VALUES (3, 'bbb', '$2a$10$blJ4Qgbaqxm5jmUAWvuiRuKy/FiqbmFv.n1i0noM3pxUZrYhd2HNK', '小黑', 'student', 'xiaohei@163.com', '13799886699', '/uploads/1790046917012_b9ee534a.png', 1, '2026-09-22 11:15:00', '2026-09-22 11:15:30');

-- ----------------------------
-- 课程信息
-- ----------------------------
CREATE TABLE `courses`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `name` varchar(100) NOT NULL COMMENT '课程名称',
  `code` varchar(50) NULL DEFAULT NULL COMMENT '课程代码',
  `description` text NULL COMMENT '课程简介',
  `status` int NOT NULL DEFAULT 1 COMMENT '状态：0-停用，1-正常',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `code`(`code` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '课程信息';

INSERT INTO `courses` (`id`, `name`, `code`, `description`, `status`) VALUES
(1, '大学英语', 'ENG101', '听说读写综合训练', 1),
(2, '数据结构', 'DS101', '线性表、树、图与常用算法', 1),
(3, '高等数学', 'MATH101', '极限、导数与积分', 1);

-- ----------------------------
-- 课表信息（演示数据按 今天 / 明天 / 后天 写入）
-- ----------------------------
CREATE TABLE `schedules`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` int NOT NULL COMMENT '学生ID',
  `class_date` date NOT NULL COMMENT '上课日期',
  `period` varchar(50) NOT NULL COMMENT '节次',
  `course_id` int NOT NULL COMMENT '课程ID',
  `location` varchar(100) NULL DEFAULT NULL COMMENT '地点',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_date`(`user_id` ASC, `class_date` ASC) USING BTREE,
  CONSTRAINT `fk_schedule_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_schedule_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`) ON DELETE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '课表信息';

INSERT INTO `schedules` (`user_id`, `class_date`, `period`, `course_id`, `location`) VALUES
(2, CURDATE(), '1-2节', 1, '教学楼 A201'),
(2, DATE_ADD(CURDATE(), INTERVAL 1 DAY), '3-4节', 2, '教学楼 B305'),
(2, DATE_ADD(CURDATE(), INTERVAL 2 DAY), '1-2节', 3, '教学楼 A102');

-- ----------------------------
-- 学习计划（turn_id 用于 MCP 同轮去重，手动保存为 NULL）
-- ----------------------------
CREATE TABLE `study_plans`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` int NOT NULL COMMENT '用户ID',
  `content` text NOT NULL COMMENT '计划内容',
  `turn_id` varchar(32) NULL DEFAULT NULL COMMENT 'MCP对话轮次ID',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_study_plan_user_turn`(`user_id` ASC, `turn_id` ASC) USING BTREE,
  CONSTRAINT `fk_plan_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '学习计划';

INSERT INTO `study_plans` (`user_id`, `content`, `turn_id`) VALUES
(2, '明天数据结构课前，把链表与二叉树笔记过一遍，并完成课后习题 1～3。', NULL),
(2, '## 本周复习\n\n- 高等数学：导数练习\n- 大学英语：Unit 3 单词', NULL);

-- ----------------------------
-- 知识库文档记录（原文件位于 backend/data/kb，向量位于 Chroma）
-- ----------------------------
CREATE TABLE `kb_documents`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `original_name` varchar(255) NOT NULL COMMENT '原始文件名',
  `disk_name` varchar(255) NOT NULL COMMENT '磁盘文件名',
  `rel_path` varchar(512) NOT NULL COMMENT '相对 data/kb 的路径',
  `size` int NOT NULL COMMENT '文件字节数',
  `ext` varchar(20) NOT NULL COMMENT '小写扩展名',
  `ingested` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否已写入共享向量库',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `original_name`(`original_name` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '知识库文档';

SET FOREIGN_KEY_CHECKS = 1;
