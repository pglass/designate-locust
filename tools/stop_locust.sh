TMP_COOKIE_FILE=tmp.cookie
curl -c $TMP_COOKIE_FILE --digest -u imauser:imapassword "localhost:8089/stop"
rm $TMP_COOKIE_FILE
