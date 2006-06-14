
import gobject
import libvirt

class vmmDomain(gobject.GObject):
    __gsignals__ = {
        "status-changed": (gobject.SIGNAL_RUN_FIRST,
                           gobject.TYPE_NONE,
                           [int]),
        "resources-sampled": (gobject.SIGNAL_RUN_FIRST,
                              gobject.TYPE_NONE,
                              []),
        }

    def __init__(self, config, connection, vm, uuid):
        self.__gobject_init__()
        self.config = config
        self.connection = connection
        self.vm = vm
        self.uuid = uuid
        self.lastStatus = None
        self.record = []

    def get_connection(self):
        return self.connection

    def get_name(self):
        return self.vm.name()

    def get_uuid(self):
        return self.uuid

    def _normalize_status(self, status):
        if self.lastStatus == libvirt.VIR_DOMAIN_NOSTATE:
            return libvirt.VIR_DOMAIN_RUNNING
        elif self.lastStatus == libvirt.VIR_DOMAIN_BLOCKED:
            return libvirt.VIR_DOMAIN_RUNNING
        return status

    def _update_status(self, status=None):
        if status == None:
            info = self.vm.info()
            status = info[0]
        status = self._normalize_status(status)
        print "Update status check " + str(status) + " old " + str(self.lastStatus)
        if status != self.lastStatus:
            self.lastStatus = status
            self.emit("status-changed", status)

    def tick(self, now):
        hostInfo = self.connection.get_host_info()
        info = self.vm.info()
        expected = self.config.get_stats_history_length()
        current = len(self.record)
        if current > expected:
            del self.record[expected:current]

        prevCpuTime = 0
        prevTimestamp = 0
        if len(self.record) > 0:
            prevTimestamp = self.record[0]["timestamp"]
            prevCpuTime = self.record[0]["cpuTimeAbs"]

        cpuTime = 0
        cpuTimeAbs = 0
        pcentCpuTime = 0
        if not(info[0] in [libvirt.VIR_DOMAIN_SHUTOFF, libvirt.VIR_DOMAIN_CRASHED]):
            cpuTime = info[4] - prevCpuTime
            cpuTimeAbs = info[4]
            pcentCpuTime = (cpuTime) * 100 / ((now - prevTimestamp)*1000*1000*1000*self.connection.host_active_processor_count())

        pcentCurrMem = info[2] * 100 / self.connection.host_memory_size()
        pcentMaxMem = info[1] * 100 / self.connection.host_memory_size()

        newStats = { "timestamp": now,
                     "cpuTime": cpuTime,
                     "cpuTimeAbs": cpuTimeAbs,
                     "cpuTimePercent": pcentCpuTime,
                     "currMem": info[2],
                     "currMemPercent": pcentCurrMem,
                     "maxMem": info[1],
                     "maxMemPercent": pcentMaxMem,
                     }
        print "Update " + str(newStats)
        self.record.insert(0, newStats)

        nSamples = 5
        #nSamples = len(self.record)
        if nSamples > len(self.record):
            nSamples = len(self.record)

        startCpuTime = self.record[nSamples-1]["cpuTimeAbs"]
        startTimestamp = self.record[nSamples-1]["timestamp"]

        if startTimestamp == now:
            self.record[0]["cpuTimeMovingAvg"] = self.record[0]["cpuTimeAbs"]
            self.record[0]["cpuTimeMovingAvgPercent"] = 0
        else:
            self.record[0]["cpuTimeMovingAvg"] = (self.record[0]["cpuTimeAbs"]-startCpuTime) / nSamples
            self.record[0]["cpuTimeMovingAvgPercent"] = (self.record[0]["cpuTimeAbs"]-startCpuTime) * 100 / ((now-startTimestamp)*1000*1000*1000 * self.connection.host_active_processor_count())

        self._update_status(info[0])
        self.emit("resources-sampled")


    def current_memory(self):
        if len(self.record) == 0:
            return 0
        return self.record[0]["currMem"]

    def current_memory_percentage(self):
        if len(self.record) == 0:
            return 0
        return self.record[0]["currMemPercent"]

    def maximum_memory(self):
        if len(self.record) == 0:
            return 0
        return self.record[0]["maxMem"]

    def maximum_memory_percentage(self):
        if len(self.record) == 0:
            return 0
        return self.record[0]["maxMemPercent"]

    def cpu_time(self):
        if len(self.record) == 0:
            return 0
        return self.record[0]["cpuTime"]

    def cpu_time_percentage(self):
        if len(self.record) == 0:
            return 0
        return self.record[0]["cpuTimePercent"]

    def network_traffic(self):
        return 1

    def network_traffic_percentage(self):
        return 1

    def disk_usage(self):
        return 1

    def disk_usage_percentage(self):
        return 1

    def cpu_time_vector(self):
        vector = []
        stats = self.record
        for i in range(self.config.get_stats_history_length()+1):
            if i < len(stats):
                vector.append(stats[i]["cpuTimePercent"])
            else:
                vector.append(0)
        return vector

    def cpu_time_moving_avg_vector(self):
        vector = []
        stats = self.record
        for i in range(self.config.get_stats_history_length()+1):
            if i < len(stats):
                vector.append(stats[i]["cpuTimeMovingAvgPercent"])
            else:
                vector.append(0)
        return vector

    def current_memory_vector(self):
        vector = []
        stats = self.record
        for i in range(self.config.get_stats_history_length()+1):
            if i < len(stats):
                vector.append(stats[i]["currMemPercent"])
            else:
                vector.append(0)
        return vector

    def network_traffic_vector(self):
        vector = []
        stats = self.record
        for i in range(self.config.get_stats_history_length()+1):
            vector.append(1)
        return vector

    def disk_usage_vector(self):
        vector = []
        stats = self.record
        for i in range(self.config.get_stats_history_length()+1):
            vector.append(1)
        return vector

    def shutdown(self):
        print "Do shutdown"
        self.vm.shutdown()
        self._update_status()

    def suspend(self):
        print "Do suspend"
        self.vm.suspend()
        self._update_status()

    def resume(self):
        print "Do resume"
        self.vm.resume()
        self._update_status()

    def status(self):
        return self.lastStatus

    def run_status(self):
        if self.lastStatus == libvirt.VIR_DOMAIN_RUNNING:
            return "Running"
        elif self.lastStatus == libvirt.VIR_DOMAIN_PAUSED:
            return "Paused"
        elif self.lastStatus == libvirt.VIR_DOMAIN_SHUTDOWN:
            return "Shutdown"
        elif self.lastStatus == libvirt.VIR_DOMAIN_SHUTOFF:
            return "Shutoff"
        elif self.lastStatus == libvirt.VIR_DOMAIN_CRASHED:
            return "Crashed"
        else:
            raise "Unknown status code"

    def run_status_icon(self):
        status = self.run_status()
        return self.config.get_vm_status_icon(status.lower())


gobject.type_register(vmmDomain)
