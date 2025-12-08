echo "Waiting for RabbitMQ..."
until curl -s http://localhost:15672/api/health/checks/alarms > /dev/null; do
	sleep 2
done

for service in \
	"Extraction|8002" \
	"Ingestion|8001" \
	"Indexing|8003" \
	"Retrieval|8004" \
	"Chat|8005"
do
	name="$(echo $service | cut -d'|' -f1)"
	port="$(echo $service | cut -d'|' -f2)"
	echo "Waiting for $name Service..."
	until curl -s http://localhost:$port/health > /dev/null; do
		sleep 2
	done
done

echo "All services ready!"