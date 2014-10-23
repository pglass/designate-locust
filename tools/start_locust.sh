# make send a POST request to kick off the locust test
# for some reason, this doesn't work if we don't accept a cookie
TMP_COOKIE_FILE=tmp.cookie
curl -c $TMP_COOKIE_FILE --digest -u imauser:imapassword "localhost:8089/swarm" \
    --form "locust_count=3" --form "hatch_rate=1"
rm -f $TMP_COOKIE_FILE
