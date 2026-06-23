import logging
import math

from prometheus_client.metrics_core import GaugeMetricFamily, CounterMetricFamily


class PowerCollector:

    def __init__(self, redfish_metrics_collector):
        self.col = redfish_metrics_collector

        self.psu_health_metrics = GaugeMetricFamily(
            "redfish_psu_health",
            "Redfish Server Monitoring PSU Health Data",
            labels=self.col.labels,
        )
        self.psu_output_voltage_metrics = GaugeMetricFamily(
            "redfish_psu_output_voltage",
            "Redfish Server Monitoring PSU Output Voltage Data",
            labels=self.col.labels,
        )
        self.psu_output_amperage_metrics = GaugeMetricFamily(
            "redfish_psu_output_amperage",
            "Redfish Server Monitoring PSU Output Amperage Data",
            labels=self.col.labels,
        )
        self.psu_input_amperage_metrics = GaugeMetricFamily(
            "redfish_psu_input_amperage",
            "Redfish Server Monitoring PSU Input Amperage Data",
            labels=self.col.labels,
        )
        self.psu_power_output_watts_metrics = GaugeMetricFamily(
            "redfish_psu_power_output_watts",
            "Redfish Server Monitoring PSU Power Output Watts Data",
            labels=self.col.labels,
        )
        self.psu_power_input_watts_metrics = GaugeMetricFamily(
            "redfish_psu_power_input_watts",
            "Redfish Server Monitoring PSU Power Input Watts Data",
            labels=self.col.labels,
        )

    def collect(self):

        """Get the Power data from the Redfish API."""
        logging.debug("Target %s: Get the PDU health data.", self.col.target)
        power_data = self.col.connect_server(self.col.urls["Power"])
        if not power_data:
            return
 
        power_supplies = power_data.get("PowerSupplies", [])
        if not power_supplies:
            logging.warning("Target %s: No PowerSupplies found in Power data!", self.col.target)
            return

        for psu in power_supplies:
            psu_name = psu["Name"] if "Name" in psu and psu["Name"] is not None else "unknown"
            psu_model = psu["Model"] if "Model" in psu and psu["Model"] is not None else "unknown"
            logging.debug("Psu name: %s Psu model: %s", psu_name, psu_model)

            # Trim trailing whitespace some BMCs (Fujitsu, HPE) embed in model strings.
            if isinstance(psu_name, str):
                psu_name = psu_name.strip() or "unknown"
            if isinstance(psu_model, str):
                psu_model = psu_model.strip() or "unknown"
            psu_serial = psu.get("SerialNumber")
            if isinstance(psu_serial, str):
                psu_serial = psu_serial.strip()
                
            current_labels = {
                "device_type": "powersupply",
                "device_name": psu_name,
                "device_model": psu_model,
                "id": psu.get("MemberId") or psu.get("Id") or "unknown",
                "serial": psu_serial or "n/a",
            }
            current_labels.update(self.col.labels)
            psu_health = self.extract_health_status(psu, "PSU", psu_name)
            self.add_metric_sample(
                "redfish_psu_health",
                {"Health": psu_health},
                "Health",
                current_labels
            )
            psu_output_voltage = self.extract_output_voltage(psu, "PSU", psu_name)
            self.add_metric_sample(
                "redfish_psu_output_voltage",
                {"OutputVoltage": psu_output_voltage},
                "OutputVoltage",
                current_labels
            )
            psu_output_amperage = self.extract_output_amperage(psu, "PSU", psu_name)
            self.add_metric_sample(
                "redfish_psu_output_amperage",
                {"OutputAmperage": psu_output_amperage},
                "OutputAmperage",
                current_labels
            )
            psu_input_amperage = self.extract_input_amperage(psu, "PSU", psu_name)
            self.add_metric_sample(
                "redfish_psu_input_amperage",
                {"InputAmperage": psu_input_amperage},
                "InputAmperage",
                current_labels
            )
            psu_power_output_watts = self.extract_power_output_watts(psu, "PSU", psu_name)
            self.add_metric_sample(
                "redfish_psu_power_output_watts",
                {"PowerOutputWatts": psu_power_output_watts},
                "PowerOutputWatts",
                current_labels
            )
            psu_power_input_watts = self.extract_power_input_watts(psu, "PSU", psu_name)
            self.add_metric_sample(
                "redfish_psu_power_input_watts",
                {"PowerInputWatts": psu_power_input_watts},
                "PowerInputWatts",
                current_labels
            )

    def extract_health_status(self, data, device_type, device_name):
        """Extract health status from data."""
        if "Status" not in data:
            return math.nan

        status = data["Status"]
        if isinstance(status, str):
            return self.col.status[status.lower()]

        status = {k.lower(): v for k, v in status.items()}
        state = status.get("state")
        if state is None or state.lower() == "absent":
            logging.debug(
                "Target %s: Host %s, Model %s, %s %s: absent.",
                self.col.target,
                self.col.host,
                self.col.model,
                device_type,
                device_name
            )
            return math.nan

        health = status.get("health", "")
        if not health:
            logging.warning(
                "Target %s: No %s health data provided for %s!",
                self.col.target,
                device_type,
                device_name
            )
            return math.nan

        return self.col.status[health.lower()]

    def extract_output_voltage(self, data, device_type, device_name):
        """Extract output voltage from data."""
        vendor = self.get_vendor_oem(data, device_type, device_name)
    
        if vendor is None:
            return math.nan
    
        voltage = vendor.get("OutputVoltage")
        if voltage is None:
            logging.warning(
                "Target %s: No %s output voltage data provided for %s!",
                self.col.target,
                device_type,
                device_name
            )
            return math.nan
    
        return voltage
    
    def extract_output_amperage(self, data, device_type, device_name):
        """Extract output amperage from data."""
        vendor = self.get_vendor_oem(data, device_type, device_name)
    
        if vendor is None:
            return math.nan
    
        amperage = vendor.get("OutputAmperage")
        if amperage is None:
            logging.warning(
                "Target %s: No %s output amperage data provided for %s!",
                self.col.target,
                device_type,
                device_name
            )
            return math.nan
    
        return amperage

    def extract_input_amperage(self, data, device_type, device_name):
        """Extract output amperage from data."""
        vendor = self.get_vendor_oem(data, device_type, device_name)
    
        if vendor is None:
            return math.nan
    
        amperage = vendor.get("InputAmperage")
        if amperage is None:
            logging.warning(
                "Target %s: No %s input amperage data provided for %s!",
                self.col.target,
                device_type,
                device_name
            )
            return math.nan
    
        return amperage

    def extract_power_output_watts(self, data, device_type, device_name):
        """Extract output watts from data."""
        vendor = self.get_vendor_oem(data, device_type, device_name)
    
        if vendor is None:
            return math.nan
    
        watts = vendor.get("PowerOutputWatts")
        if watts is None:
            logging.warning(
                "Target %s: No %s power output watts data provided for %s!",
                self.col.target,
                device_type,
                device_name
            )
            return math.nan
    
        return watts

    def extract_power_input_watts(self, data, device_type, device_name):
        """Extract output watts from data."""
        vendor = self.get_vendor_oem(data, device_type, device_name)
    
        if vendor is None:
            return math.nan
    
        watts = vendor.get("PowerInputWatts")
        if watts is None:
            logging.warning(
                "Target %s: No %s power input watts data provided for %s!",
                self.col.target,
                device_type,
                device_name
            )
            return math.nan
    
        return watts

    def add_metric_sample(self, metric_name, data, key, labels):
        """Add a sample to the specified metric."""
        try:
            value = float(data[key]) if data.get(key) is not None else math.nan
        except (ValueError, TypeError):
            value = math.nan

        if math.isnan(value):
            logging.debug(
                "Target %s: Host %s, Model %s, Name %s: No %s Metrics found.",
                self.col.target,
                self.col.host,
                self.col.model,
                labels["device_name"],
                key
            )
        else:
            if metric_name == "redfish_psu_health":
                metric_family = self.psu_health_metrics
            elif metric_name == "redfish_psu_output_voltage":
                metric_family = self.psu_output_voltage_metrics
            elif metric_name == "redfish_psu_output_amperage":
                metric_family = self.psu_output_amperage_metrics
            elif metric_name == "redfish_psu_input_amperage":
                metric_family = self.psu_input_amperage_metrics
            elif metric_name == "redfish_psu_power_output_watts":
                metric_family = self.psu_power_output_watts_metrics
            elif metric_name == "redfish_psu_power_input_watts":
                metric_family = self.psu_power_input_watts_metrics
            else:
                metric_family = getattr(self, f"mem_metrics_{metric_name.split('_')[-1]}")
            metric_family.add_sample(metric_name, value=value, labels=labels)

    def get_vendor_oem(self, data, device_type, device_name):
        """Get the vendor (Oem->Huawei or Oem->xFusion) dictionary."""
        vendor = data.get("Oem", {}).get("Huawei")

        if vendor is None:
            vendor = data.get("Oem", {}).get("xFusion")
    
        if vendor is None:
            logging.debug(
                "Target %s: Host %s, Model %s, %s %s: Oem->[Vendor] entry not found.",
                self.col.target,
                self.col.host,
                self.col.model,
                device_type,
                device_name
            )
    
        return vendor
