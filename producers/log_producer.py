import json
import random
import time
import os
from datetime import datetime
from kafka import KafkaProducer

class LogProducer:
    def __init__(self, kafka_broker, topic_name):
        self.kafka_broker = kafka_broker
        self.topic_name = topic_name
        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_broker,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
            retries=3
        )
        
        self.log_templates = [
            'User {user_id} accessed {endpoint}',
            'Error processing request {request_id}: {error_msg}',
            'Database query took {query_time}ms',
            'Service {service_name} started successfully',
            'Failed to connect to {external_service}'
        ]
        
        self.log_levels = ['INFO', 'WARN', 'ERROR', 'DEBUG']
        self.services = ['auth-service', 'payment-service', 'inventory-service', 
                        'order-service', 'notification-service']

    def generate_log(self):
        template = random.choice(self.log_templates)
        log_level = random.choice(self.log_levels)
        service = random.choice(self.services)
        
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": service,
            "level": log_level,
            "message": template.format(
                user_id=random.randint(1000, 9999),
                endpoint=random.choice(['/api/users', '/api/orders', '/api/payments']),
                request_id=str(random.randint(100000, 999999)),
                error_msg=random.choice(['Timeout', 'Invalid input', 'Database connection failed']),
                query_time=random.randint(10, 500),
                service_name=service,
                external_service=random.choice(['payment-gateway', 'email-service', 'sms-service'])
            ),
            "metadata": {
                "host": f"host-{random.randint(1, 10)}",
                "region": random.choice(['us-east', 'us-west', 'eu-central'])
            }
        }
        
        return log_data

    def produce_logs(self):
        try:
            while True:
                log = self.generate_log()
                self.producer.send(self.topic_name, value=log)
                print(f"Produced log: {log}")
                time.sleep(random.uniform(0.1, 1.0))
        except KeyboardInterrupt:
            self.producer.close()

if __name__ == "__main__":
    kafka_broker = os.getenv('KAFKA_BROKER', 'localhost:29092')
    topic_name = os.getenv('TOPIC_NAME', 'app_logs')
    
    producer = LogProducer(kafka_broker, topic_name)
    producer.produce_logs()