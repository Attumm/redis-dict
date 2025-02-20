import redis_dict

from queue import Queue


if __name__ == '__main__':
    q = Queue()
    r = redis_dict.RedisDict(host="redis", namespace="suggestion", output_queue=q)

    # prove redis is working
    print(r.get("test_key"))
    r.subscribe("suggestion:test_key")
    r.start_pubsub()

    while True:
        if q.qsize() > 0:
            message = q.get()
            print("Received message: %s" % message)
            print("message type: %s" % message['type'])
            print("message pattern: %s" % message['pattern'])
            print(r.get("test_key"))

            # unsubscribe not working, report io socket error
            # r.unsubscribe()
