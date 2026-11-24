[app]

title = إدارة مياه القرية
package.name = watermanagement
package.domain = org.village.water
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf
version = 1.0

requirements = python3,kivy,cython,arabic-reshaper,python-bidi,pyjnius,android

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a, armeabi-v7a
android.permissions = INTERNET
android.api = 33
android.minapi = 21

[buildozer]

log_level = 2
warn_on_root = 1
