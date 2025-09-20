import struct
import time

class TemperatureLogger:
    def __init__(self, max_readings=2880, min_interval_minutes=5):
        """
        Custom ring buffer temperature logger with latest-wins storage
        
        Args:
            max_readings: Maximum number of readings to store
            min_interval_minutes: Minimum minutes between stored readings per sensor
        """
        self.record_size = 5
        self.max_readings = max_readings
        buffer_size = max_readings * self.record_size
        
        # Custom ring buffer using bytearray
        self.buffer = bytearray(buffer_size)
        self.head = 0  # Write position (next slot to write)
        self.tail = 0  # Read position (oldest data)
        self.count = 0  # Number of records currently stored
        
        self.start_time = time.time()
        self.min_interval_seconds = min_interval_minutes * 60
        
        # Dynamic sensor tracking
        self.name_to_id = {}      # sensor_name -> sensor_id
        self.id_to_name = {}      # sensor_id -> sensor_name
        self.next_sensor_id = 0   # Next available sensor ID
        
        # Track last STORAGE time for each sensor (not just last received)
        self.last_stored_time = {}  # sensor_name -> timestamp when last stored
        
        # NEW: Store detailed information for the last reading from each sensor
        self.last_detailed_readings = {}  # sensor_name -> detailed_info_dict
        
        print(f"Custom ring buffer initialized: {max_readings} readings, {buffer_size} bytes")
        print(f"Min interval: {min_interval_minutes} minutes per sensor (latest-wins)")
    
    def _get_or_create_sensor_id(self, sensor_name):
        # Get existing sensor ID or create new one
        if sensor_name in self.name_to_id:
            return self.name_to_id[sensor_name]
        
        if self.next_sensor_id > 255:
            raise ValueError("Maximum 256 sensors supported")
        
        sensor_id = self.next_sensor_id
        self.name_to_id[sensor_name] = sensor_id
        self.id_to_name[sensor_id] = sensor_name
        self.next_sensor_id += 1
        
        print(f"New sensor registered: '{sensor_name}' -> ID {sensor_id}")
        return sensor_id
    
    def add_reading(self, sensor_name, temperature):
        """
        Add temperature reading with proper 5-minute spacing:
        - Only store NEW readings if 5+ minutes have passed since last STORAGE
        - Otherwise, update the existing reading in place
        """
        current_time = time.time()
        
        # Check when we last STORED a reading for this sensor
        last_storage_time = self.last_stored_time.get(sensor_name, 0)
        time_since_last_storage = current_time - last_storage_time
        
        if time_since_last_storage >= self.min_interval_seconds:
            # Store as new reading
            self._store_new_reading(sensor_name, temperature, current_time)
            self.last_stored_time[sensor_name] = current_time
        else:
            # Update existing reading in place
            if not self._update_existing_reading(sensor_name, temperature, current_time):
                # Fallback: store as new if update failed
                self._store_new_reading(sensor_name, temperature, current_time)
                self.last_stored_time[sensor_name] = current_time
        
        return True
    
    async def add_detailed_reading(self, sensor_name, temperature, humidity=None, battery_level=None, 
                           rssi=None, voltage=None, power=None):
        """
        Add a detailed reading with additional sensor information.
        This will store the temperature in the ring buffer (following normal interval rules)
        AND store all detailed info for the last reading.
        
        Args:
            sensor_name: Name of the sensor
            temperature: Temperature reading (required)
            humidity: Humidity percentage (optional)
            battery_level: Battery level percentage (optional)
            rssi: Signal strength in dBm (optional)
            voltage: Voltage reading (optional)
            power: Power reading (optional)
        """
        current_time = time.time()
        
        # Store temperature in ring buffer using existing logic
        self.add_reading(sensor_name, temperature)
        
        # Get or create sensor ID for detailed storage
        sensor_id = self._get_or_create_sensor_id(sensor_name)
        
        # Always update the detailed last reading (no interval restrictions)
        self.last_detailed_readings[sensor_name] = {
            'sensor_id': sensor_id,
            'sensor_name': sensor_name,
            'temperature': temperature,
            'humidity': humidity,
            'battery_level': battery_level,
            'rssi': rssi,
            'voltage': voltage,
            'power': power,
            'last_updated': current_time
        }
        
        return True
    
    def get_last_detailed_reading(self, sensor_name):
        """
        Get the last detailed reading for a specific sensor.
        
        Returns:
            Dict with detailed sensor info or None if sensor not found
        """
        return self.last_detailed_readings.get(sensor_name)
    
    def get_all_last_detailed_readings(self):
        """
        Get the last detailed readings for all sensors.
        
        Returns:
            Dict: {sensor_name: detailed_info_dict}
        """
        return self.last_detailed_readings.copy()
    
    def get_last_detailed_readings_summary(self, max_age_minutes=60):
        """
        Get a summary of all last detailed readings with age filtering.
        
        Args:
            max_age_minutes: Only include readings newer than this (None for all)
            
        Returns:
            Dict: {sensor_name: detailed_info_dict} for recent readings
        """
        if max_age_minutes is None:
            return self.get_all_last_detailed_readings()
        
        current_time = time.time()
        max_age_seconds = max_age_minutes * 60
        
        recent_readings = {}
        for sensor_name, reading in self.last_detailed_readings.items():
            age_seconds = current_time - reading['last_updated']
            if age_seconds <= max_age_seconds:
                # Add age info to the reading
                reading_with_age = reading.copy()
                reading_with_age['age_minutes'] = round(age_seconds / 60, 1)
                recent_readings[sensor_name] = reading_with_age
        
        return recent_readings
    
    def print_detailed_readings_report(self, max_age_minutes=60):
        """Print a formatted report of all last detailed readings"""
        readings = self.get_last_detailed_readings_summary(max_age_minutes)
        
        if not readings:
            print(f"No detailed readings available (within {max_age_minutes} minutes)")
            return
        
        print(f"\n=== Last Detailed Readings Report ===")
        print(f"Showing readings from last {max_age_minutes} minutes")
        print()
        
        # Header
        print(f"{'Sensor':<15} {'Temp':<6} {'Humid':<6} {'Batt':<5} {'RSSI':<6} {'Volt':<6} {'Power':<7} {'Age'}")
        print("-" * 70)
        
        # Sort by sensor name for consistent output
        for sensor_name in sorted(readings.keys()):
            data = readings[sensor_name]
            
            # Format values with None handling
            temp = f"{data['temperature']:.1f}" if data['temperature'] is not None else "---"
            humid = f"{data['humidity']:.1f}%" if data['humidity'] is not None else "---"
            batt = f"{data['battery_level']:.0f}%" if data['battery_level'] is not None else "---"
            rssi = f"{data['rssi']:.0f}" if data['rssi'] is not None else "---"
            volt = f"{data['voltage']:.2f}V" if data['voltage'] is not None else "---"
            power = f"{data['power']:.1f}W" if data['power'] is not None else "---"
            age = f"{data['age_minutes']:.1f}m"
            
            print(f"{sensor_name:<15} {temp:<6} {humid:<6} {batt:<5} {rssi:<6} {volt:<6} {power:<7} {age}")
        
        print(f"\nTotal sensors with detailed readings: {len(readings)}")
    
    def export_detailed_readings_csv(self):
        """Export all last detailed readings as CSV string"""
        readings = self.get_all_last_detailed_readings()
        
        if not readings:
            return "No detailed readings available"
        
        # CSV header
        csv_lines = [
            "sensor_name,sensor_id,temperature,humidity,battery_level,rssi,voltage,power,last_updated"
        ]
        
        # Sort by sensor name for consistent output
        for sensor_name in sorted(readings.keys()):
            data = readings[sensor_name]
            
            # Handle None values
            def format_value(val):
                return str(val) if val is not None else ""
            
            line = f"{sensor_name},{data['sensor_id']},{format_value(data['temperature'])}," \
                   f"{format_value(data['humidity'])},{format_value(data['battery_level'])}," \
                   f"{format_value(data['rssi'])},{format_value(data['voltage'])}," \
                   f"{format_value(data['power'])},{int(data['last_updated'])}"
            
            csv_lines.append(line)
        
        return "\n".join(csv_lines)
    
    def get_sensor_detailed_status(self, sensor_name):
        """
        Get comprehensive status for a specific sensor including both detailed and historical data.
        
        Returns:
            Dict with both last detailed reading and recent history summary
        """
        detailed = self.get_last_detailed_reading(sensor_name)
        historical = self.get_sensor_stats(sensor_name, hours=24)
        
        if detailed is None and historical is None:
            return None
        
        current_time = time.time()
        
        result = {
            'sensor_name': sensor_name,
            'has_detailed_reading': detailed is not None,
            'has_historical_data': historical is not None
        }
        
        if detailed:
            result['last_detailed'] = detailed.copy()
            result['last_detailed']['age_minutes'] = round(
                (current_time - detailed['last_updated']) / 60, 1
            )
        
        if historical:
            result['daily_stats'] = historical
        
        return result
    
    # Keep all the existing methods unchanged below this point...
    
    def _update_existing_reading(self, sensor_name, temperature, timestamp):
        """
        Find and update the most recent reading for this sensor in the buffer.
        This doesn't add a new record, just updates an existing one.
        """
        if sensor_name not in self.name_to_id:
            return False
            
        sensor_id = self.name_to_id[sensor_name]
        
        # Search backwards from head to find most recent reading for this sensor
        pos = (self.head - 1) % self.max_readings
        
        for i in range(self.count):
            start_byte = pos * self.record_size
            record_data = self.buffer[start_byte:start_byte + self.record_size]
            
            try:
                _, stored_sensor_id, _ = struct.unpack('<HBh', record_data)
                if stored_sensor_id == sensor_id:
                    # Found the most recent reading for this sensor - update it
                    self._overwrite_reading_at_position(pos, sensor_name, temperature, timestamp)
                    return True
            except:
                pass
                
            pos = (pos - 1) % self.max_readings
        
        return False
    
    def _overwrite_reading_at_position(self, position, sensor_name, temperature, timestamp):
        """Overwrite the reading at the specified ring buffer position"""
        sensor_id = self.name_to_id[sensor_name]
        
        # Calculate relative time
        relative_minutes = int((timestamp - self.start_time) / 60)
        if relative_minutes > 65535:
            self._reset_time_reference()
            relative_minutes = 0
        
        # Pack new data
        temp_scaled = int(temperature * 100)
        data = struct.pack('<HBh', relative_minutes, sensor_id, temp_scaled)
        
        # Overwrite at position
        start_byte = position * self.record_size
        end_byte = start_byte + self.record_size
        self.buffer[start_byte:end_byte] = data
    
    def _store_new_reading(self, sensor_name, temperature, timestamp):
        """Store a completely new reading (append to ring buffer)"""
        sensor_id = self._get_or_create_sensor_id(sensor_name)
        
        # Calculate relative time
        relative_minutes = int((timestamp - self.start_time) / 60)
        if relative_minutes > 65535:
            self._reset_time_reference()
            relative_minutes = 0
        
        # Pack data
        temp_scaled = int(temperature * 100)
        data = struct.pack('<HBh', relative_minutes, sensor_id, temp_scaled)
        
        # Append to ring buffer
        start_pos = self.head * self.record_size
        end_pos = start_pos + self.record_size
        self.buffer[start_pos:end_pos] = data
        
        # Update ring buffer pointers
        self.head = (self.head + 1) % self.max_readings
        
        if self.count < self.max_readings:
            self.count += 1
        else:
            # Buffer full, advance tail (overwrite oldest)
            self.tail = (self.tail + 1) % self.max_readings
    
    def _reset_time_reference(self):
        """Reset time reference when approaching 45-day limit"""
        print("Resetting time reference (45-day limit reached)")
        self.start_time = time.time()
    
    def _parse_record(self, record_data):
        """Parse a single record from binary data"""
        try:
            relative_minutes, sensor_id, temp_scaled = struct.unpack('<HBh', record_data)
            
            timestamp = self.start_time + (relative_minutes * 60)
            temperature = temp_scaled / 100.0
            sensor_name = self.id_to_name.get(sensor_id, f"unknown_{sensor_id}")
            
            return timestamp, sensor_name, temperature
            
        except (struct.error, KeyError):
            return None
    
    def _get_records_in_range(self, max_age_seconds=None, max_count=None):
        """
        Get records from ring buffer - NON-DESTRUCTIVE
        
        Args:
            max_age_seconds: Only return records newer than this
            max_count: Maximum number of records to return (most recent)
        
        Returns:
            List of (timestamp, sensor_name, temperature) tuples
        """
        if self.count == 0:
            return []
        
        current_time = time.time()
        
        if max_age_seconds is not None:
            cutoff_time = current_time - max_age_seconds
        else:
            cutoff_time = 0  # Include all records if no age limit
        
        all_valid_records = []
        
        # Scan all records in the ring buffer
        pos = self.tail
        for i in range(self.count):
            start_byte = pos * self.record_size
            end_byte = start_byte + self.record_size
            record_data = self.buffer[start_byte:end_byte]
            
            parsed = self._parse_record(record_data)
            if parsed:
                timestamp, sensor_name, temperature = parsed
                
                # Include if within time window
                if timestamp >= cutoff_time:
                    all_valid_records.append((timestamp, sensor_name, temperature))
            
            pos = (pos + 1) % self.max_readings
        
        # Sort by timestamp (chronological order)
        all_valid_records.sort(key=lambda x: x[0])
        
        # Return most recent records if count limit specified
        if max_count and len(all_valid_records) > max_count:
            return all_valid_records[-max_count:]
        
        return all_valid_records
    
    def get_all_current_temps(self, max_age_minutes=60):
        """
        Get current temperatures from all sensors - NON-DESTRUCTIVE
        
        Returns:
            Dict: {sensor_name: temperature}
        """
        max_age_seconds = max_age_minutes * 60
        
        # Get records from ring buffer
        recent_records = self._get_records_in_range(max_age_seconds)
        
        if not recent_records:
            return {}
        
        # Find latest reading per sensor
        latest_by_sensor = {}
        for timestamp, sensor_name, temperature in recent_records:
            if (sensor_name not in latest_by_sensor or 
                timestamp > latest_by_sensor[sensor_name][0]):
                latest_by_sensor[sensor_name] = (timestamp, temperature)
        
        return {name: temp for name, (_, temp) in latest_by_sensor.items()}
    
    def get_daily_records_by_sensor(self, hours=24):
        """
        Get daily records organized by sensor - NON-DESTRUCTIVE
        
        Args:
            hours: Number of hours of history to retrieve
            
        Returns:
            Dict: {sensor_name: [(timestamp, temperature), ...]}
        """
        max_age_seconds = hours * 3600
        
        # Get only records in the time window
        records = self._get_records_in_range(max_age_seconds)
        
        if not records:
            return {}
        
        # Group by sensor
        records_by_sensor = {}
        for timestamp, sensor_name, temperature in records:
            if sensor_name not in records_by_sensor:
                records_by_sensor[sensor_name] = []
            records_by_sensor[sensor_name].append((timestamp, temperature))
        
        # Already in chronological order from _get_records_in_range
        return records_by_sensor
    
    def get_recent_readings(self, count=200):
        """
        Get recent readings from all sensors - NON-DESTRUCTIVE
        
        Returns:
            List of tuples: (timestamp, sensor_name, temperature)
        """
        records = self._get_records_in_range(max_count=count)
        return records
    
    def get_current_state(self, max_age_minutes=60):
        """
        Get latest reading from each sensor with metadata - NON-DESTRUCTIVE
        
        Returns:
            Dict: {sensor_name: {'temperature': temp, 'timestamp': ts, 'age_minutes': age}}
        """
        max_age_seconds = max_age_minutes * 60
        current_time = time.time()
        
        recent_records = self._get_records_in_range(max_age_seconds)
        
        if not recent_records:
            return {}
        
        # Find latest reading per sensor with metadata
        latest_by_sensor = {}
        for timestamp, sensor_name, temperature in recent_records:
            if (sensor_name not in latest_by_sensor or 
                timestamp > latest_by_sensor[sensor_name]['timestamp']):
                age_minutes = (current_time - timestamp) / 60
                latest_by_sensor[sensor_name] = {
                    'temperature': temperature,
                    'timestamp': timestamp,
                    'age_minutes': round(age_minutes, 1)
                }
        
        return latest_by_sensor
    
    def get_daily_summary_by_sensor(self, hours=24):
        """
        Get summary statistics for all sensors over last N hours - NON-DESTRUCTIVE
        
        Returns:
            Dict: {sensor_name: {'count': N, 'min': temp, 'max': temp, 'avg': temp, 'latest': temp}}
        """
        daily_records = self.get_daily_records_by_sensor(hours)
        summary = {}
        current_time = time.time()
        
        for sensor_name, readings in daily_records.items():
            if not readings:
                continue
                
            temps = [temp for _, temp in readings]
            latest_timestamp, latest_temp = readings[-1]
            
            summary[sensor_name] = {
                'count': len(temps),
                'min': min(temps),
                'max': max(temps),
                'avg': round(sum(temps) / len(temps), 2),
                'latest': latest_temp,
                'latest_age_minutes': round((current_time - latest_timestamp) / 60, 1),
                'hours_covered': hours
            }
        
        return summary
    
    def print_daily_report(self, hours=24):
        """Print a nice summary of all sensors over the last N hours - NON-DESTRUCTIVE"""
        summary = self.get_daily_summary_by_sensor(hours)
        
        if not summary:
            print(f"No data available for last {hours} hours")
            return
        
        print(f"\n=== Temperature Report - Last {hours} Hours ===")
        print(f"{'Sensor':<15} {'Count':<6} {'Min':<6} {'Max':<6} {'Avg':<6} {'Latest':<7} {'Age'}")
        print("-" * 65)
        
        for sensor_name in sorted(summary.keys()):
            data = summary[sensor_name]
            print(f"{sensor_name:<15} {data['count']:<6} "
                  f"{data['min']:<6.1f} {data['max']:<6.1f} {data['avg']:<6.1f} "
                  f"{data['latest']:<7.1f} {data['latest_age_minutes']:.1f}m")
        
        print(f"\nTotal sensors: {len(summary)}")
    
    def get_memory_info(self):
        """Get memory usage information"""
        buffer_size_bytes = len(self.buffer)
        
        return {
            'used_records': self.count,
            'max_records': self.max_readings,
            'used_bytes': self.count * self.record_size,
            'max_bytes': buffer_size_bytes,
            'percent_full': round((self.count / self.max_readings) * 100, 2),
            'bytes_per_record': self.record_size,
            'sensor_count': len(self.name_to_id),
            'detailed_readings_count': len(self.last_detailed_readings),
            'days_running': round((time.time() - self.start_time) / 86400, 2),
            'is_buffer_full': self.count >= self.max_readings,
            'buffer_wrapped': self.count >= self.max_readings,
            'head_position': self.head,
            'tail_position': self.tail
        }
    
    def get_storage_stats(self):
        """Get statistics about storage patterns"""
        if self.count == 0:
            return {}
        
        # Count records per sensor
        sensor_counts = {}
        pos = self.tail
        
        for i in range(self.count):
            start_byte = pos * self.record_size
            record_data = self.buffer[start_byte:start_byte + self.record_size]
            
            try:
                _, sensor_id, _ = struct.unpack('<HBh', record_data)
                sensor_name = self.id_to_name.get(sensor_id, f"unknown_{sensor_id}")
                sensor_counts[sensor_name] = sensor_counts.get(sensor_name, 0) + 1
            except:
                pass
            
            pos = (pos + 1) % self.max_readings
        
        return {
            'total_records': self.count,
            'records_per_sensor': sensor_counts,
            'average_per_sensor': self.count / len(self.name_to_id) if self.name_to_id else 0,
            'theoretical_max_per_sensor': (24 * 60) // (self.min_interval_seconds // 60),  # readings per day
            'storage_efficiency': f"{(self.count / (len(self.name_to_id) * 288)):.1%}" if self.name_to_id else "0%"  # 288 = 24hrs * 12 readings/hr
        }
    
    def print_storage_report(self):
        """Print detailed storage statistics"""
        stats = self.get_storage_stats()
        memory = self.get_memory_info()
        
        print(f"\n=== Storage Report ===")
        print(f"Total records stored: {memory['used_records']}")
        print(f"Buffer utilization: {memory['percent_full']:.1f}%")
        print(f"Detailed readings stored: {memory['detailed_readings_count']}")
        print(f"Records per sensor: {stats.get('records_per_sensor', {})}")
        print(f"Average per sensor: {stats.get('average_per_sensor', 0):.1f}")
        print(f"Expected daily max per sensor: {stats.get('theoretical_max_per_sensor', 288)}")
        print(f"Current storage efficiency: {stats.get('storage_efficiency', '0%')}")
        
        if memory['used_records'] < 50:
            print(f"⚠️  Very few records stored - system may not be accumulating data over time")
        elif memory['percent_full'] < 10:
            print(f"✅ Plenty of storage space available")
        elif memory['percent_full'] > 90:
            print(f"⚠️  Buffer nearly full - oldest data being overwritten")
    
    def export_csv(self, count=1000):
        """Export recent data as CSV string - NON-DESTRUCTIVE"""
        readings = self.get_recent_readings(count)
        
        csv_lines = ["timestamp,sensor_name,temperature"]
        for timestamp, sensor_name, temp in readings:
            csv_lines.append(f"{int(timestamp)},{sensor_name},{temp:.2f}")
        
        return "\n".join(csv_lines)
    
    def get_sensor_names(self):
        """Get list of all known sensor names"""
        return list(self.name_to_id.keys())
    
    def get_sensor_count(self):
        """Get number of registered sensors"""
        return len(self.name_to_id)
    
    def sensor_exists(self, sensor_name):
        """Check if a sensor has been registered"""
        return sensor_name in self.name_to_id
    
    def clear_all_data(self):
        """Clear all readings (keeps sensor registrations)"""
        self.head = 0
        self.tail = 0
        self.count = 0
        self.last_stored_time.clear()
        self.last_detailed_readings.clear()
        print("All readings cleared")
    
    def reset_sensors(self):
        """Clear all data and sensor registrations"""
        self.clear_all_data()
        self.name_to_id.clear()
        self.id_to_name.clear()
        self.next_sensor_id = 0
        print("All data and sensor registrations cleared")
    
    def get_sensor_history(self, sensor_name, max_readings=200):
        """
        Get recent history for a specific sensor - NON-DESTRUCTIVE
        
        Returns:
            List of tuples: (timestamp, temperature)
        """
        if sensor_name not in self.name_to_id:
            return []
        
        # Get enough hours to likely contain max_readings for this sensor
        hours_needed = max(2, max_readings // 12)  # 12 readings per hour at 5-min intervals
        daily_records = self.get_daily_records_by_sensor(hours_needed)
        
        sensor_readings = daily_records.get(sensor_name, [])
        return sensor_readings[-max_readings:] if sensor_readings else []
    
    def get_sensor_stats(self, sensor_name, hours=24):
        """Get statistics for a sensor over specified hours"""
        history = self.get_sensor_history(sensor_name, 2000)
        
        if not history:
            return None
        
        cutoff_time = time.time() - (hours * 3600)
        recent_temps = [temp for ts, temp in history if ts >= cutoff_time]
        
        if not recent_temps:
            return None
        
        return {
            'sensor_name': sensor_name,
            'count': len(recent_temps),
            'min': min(recent_temps),
            'max': max(recent_temps),
            'avg': sum(recent_temps) / len(recent_temps),
            'hours': hours
        }
    
    def get_time_since_last_storage(self, sensor_name):
        """Get seconds since we last STORED (not just received) a reading from this sensor"""
        if sensor_name not in self.last_stored_time:
            return float('inf')  # Never stored
        
        return time.time() - self.last_stored_time[sensor_name]
    
    def get_sensors_ready_for_storage(self):
        """Get list of sensors ready to store new readings (5+ minutes since last storage)"""
        ready_sensors = []
        current_time = time.time()
        
        for sensor_name in self.name_to_id.keys():
            last_storage = self.last_stored_time.get(sensor_name, 0)
            if (current_time - last_storage) >= self.min_interval_seconds:
                ready_sensors.append(sensor_name)
        
        return ready_sensors
    
    def force_new_reading_for_sensor(self, sensor_name):
        """Force the next reading from this sensor to be stored as new"""
        if sensor_name in self.last_stored_time:
            del self.last_stored_time[sensor_name]