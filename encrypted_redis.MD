
1. **Creating Self-Signed Certificate**:

   Use OpenSSL to generate a self-signed certificate:

   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout test_redis_key.pem -out test_redis_cert.pem -days 365 -nodes
   ```

   This command will create a private key `test_redis_key.pem` and a self-signed certificate `test_redis_cert.pem`.

2. **Setting Up Redis with Docker and TLS**:

   Create a `redis.conf` file:

   ```bash
   echo "port 6379
   tls-port 6380
   tls-cert-file /tls/test_redis_cert.pem
   tls-key-file /tls/test_redis_key.pem
   tls-ca-cert-file /tls/test_redis_cert.pem
   " > redis.conf
   ```

   Run a Redis Docker container with the self-signed certificate and key:

   ```bash
   docker run -v `pwd`:/tls -v `pwd`/redis.conf:/usr/local/etc/redis/redis.conf -p 6379:6379 -p 6380:6380 redis redis-server /usr/local/etc/redis/redis.conf
   ```

3. **Python Test Code**:

   Install Python Redis package, if not already installed:

   ```bash
    pip install redis-dict
   ```

   Create a `main.py` Python file with the following code:

   ```python
   from redis_dict import RedisDict

   redis_config = { 
       host: 'localhost',
       port: 6380, 
       ssl: True,
       ssl_keyfile=: 'test_redis_key.pem',
       ssl_certfile=: 'test_redis_cert.pem',
       ssl_cert_reqs: 'required',
       ssl_ca_certs: 'test_redis_cert.pem'
   }
   dic = RedisDict(redis_kwargs=redis_config)

   
   dic['foo'] = 'bar'
   print(dic['foo'])  # should return 'bar'
   ```

   This will connect to the Redis instance via TLS and set a key-value pair, then retrieve and print the value.

4. **Running the Test**:

   Run the Python script:

   ```bash
   python main.py
   ```
