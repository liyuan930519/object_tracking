std_msgs/Header header

# True when a valid target is detected in the source image.
bool visible

# Target centroid in image pixel coordinates. The origin is the top-left
# corner of the image. x and y are NaN when visible is false.
float32 x
float32 y
