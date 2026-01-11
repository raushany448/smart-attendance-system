CREATE DATABASE attendance_db;
USE attendance_db;

CREATE TABLE admin(
    username VARCHAR(50),
    password VARCHAR(50)
);

INSERT INTO admin VALUES('admin','admin');

CREATE TABLE students(
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) UNIQUE,
    student_name VARCHAR(100)
);

CREATE TABLE qr_session(
    id INT AUTO_INCREMENT PRIMARY KEY,
    subject VARCHAR(100),
    created_at DATETIME,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE attendance(
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50),
    student_name VARCHAR(100),
    subject VARCHAR(100),
    date DATE,
    time TIME
);

select * from students;

