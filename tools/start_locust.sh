if [ -z "$LOCUST_ENDPOINT" ]; then
    echo "Need LOCUST_ENDPOINT"
    exit 1
elif [ -z "$LOCUST_COUNT" ]; then
    echo "Need LOCUST_COUNT"
    exit 1
elif [ -z "$LOCUST_HATCH_RATE" ]; then
    echo "Need LOCUST_HATCH_RATE"
    exit 1
fi

if [ -z "$LOCUST_USERNAME" ]; then
    # make send a POST request to kick off the locust test
    curl "$LOCUST_ENDPOINT/swarm" \
        --form "locust_count=$LOCUST_COUNT" --form "hatch_rate=$LOCUST_HATCH_RATE"
else
    curl -u $LOCUST_USERNAME:$LOCUST_PASSWORD "$LOCUST_ENDPOINT/swarm" \
        --form "locust_count=$LOCUST_COUNT" --form "hatch_rate=$LOCUST_HATCH_RATE"
fi
