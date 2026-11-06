/*
 * sdrplay_rx - stream IQ from an SDRplay RSP as interleaved int16 (like airspyhf_rx -r -).
 *
 * Uses SoapySDR with the SoapySDRPlay3 module and the SDRplay API service
 * (image built with WITH_SDRPLAY=1). RadioMoni builds the command line in
 * radiomoni/sdrplay.py; an RSPduo tuner runs as master (--mode MA) or slave (SL).
 *
 *   sdrplay_rx --device SERIAL[:A|B] [--mode ST|MA|SL] -f HZ -s RATE [--antenna NAME]
 *              [--lna STATE] [--agc | --ifgr DB] [--setting key=value]... [-n SAMPLES] [-o FILE|-]
 *
 * Build: gcc -O2 -Wall -o sdrplay_rx sdrplay_rx.c $(pkg-config --cflags --libs SoapySDR)
 */
#include <SoapySDR/Device.h>
#include <SoapySDR/Formats.h>
#include <SoapySDR/Types.h>

#include <getopt.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_SETTINGS 16

static volatile sig_atomic_t stop_requested = 0;

static void on_signal(int sig) {
    (void)sig;
    stop_requested = 1;
}

static void usage(const char *name) {
    fprintf(stderr,
            "usage: %s --device SERIAL[:A|B] [--mode ST|MA|SL] -f HZ -s RATE [--antenna NAME]\n"
            "          [--lna STATE] [--agc | --ifgr DB] [--setting key=value]... [-n SAMPLES] [-o FILE|-]\n",
            name);
}

int main(int argc, char **argv) {
    const char *device_arg = "", *mode = NULL, *antenna = NULL, *output = "-";
    const char *settings[MAX_SETTINGS];
    int n_settings = 0, lna = -1, ifgr = -1;
    bool agc = false;
    double frequency = 0, rate = 2e6;
    long long max_samples = 0;

    static const struct option options[] = {
        {"device", required_argument, NULL, 'd'}, {"mode", required_argument, NULL, 'm'},
        {"freq", required_argument, NULL, 'f'},   {"rate", required_argument, NULL, 's'},
        {"antenna", required_argument, NULL, 'A'}, {"lna", required_argument, NULL, 'l'},
        {"agc", no_argument, NULL, 'a'},          {"ifgr", required_argument, NULL, 'i'},
        {"setting", required_argument, NULL, 'S'}, {"samples", required_argument, NULL, 'n'},
        {"output", required_argument, NULL, 'o'}, {"help", no_argument, NULL, 'h'},
        {NULL, 0, NULL, 0}};
    int opt;
    while ((opt = getopt_long(argc, argv, "d:m:f:s:A:l:ai:S:n:o:h", options, NULL)) != -1) {
        switch (opt) {
        case 'd': device_arg = optarg; break;
        case 'm': mode = optarg; break;
        case 'f': frequency = atof(optarg); break;
        case 's': rate = atof(optarg); break;
        case 'A': antenna = optarg; break;
        case 'l': lna = atoi(optarg); break;
        case 'a': agc = true; break;
        case 'i': ifgr = atoi(optarg); break;
        case 'S':
            if (n_settings < MAX_SETTINGS) settings[n_settings++] = optarg;
            break;
        case 'n': max_samples = atoll(optarg); break;
        case 'o': output = optarg; break;
        default: usage(argv[0]); return opt == 'h' ? 0 : 2;
        }
    }
    if (frequency <= 0) {
        usage(argv[0]);
        return 2;
    }

    /* SERIAL[:A|B]: the tuner only matters for the antenna, which radiomoni passes */
    char serial[64] = "";
    strncpy(serial, device_arg, sizeof(serial) - 1);
    char *colon = strchr(serial, ':');
    if (colon) *colon = '\0';

    char argstr[160];
    snprintf(argstr, sizeof(argstr), "driver=sdrplay%s%s%s%s", serial[0] ? ",serial=" : "", serial,
             mode ? ",mode=" : "", mode ? mode : "");
    SoapySDRKwargs args = SoapySDRKwargs_fromString(argstr);
    SoapySDRDevice *dev = SoapySDRDevice_make(&args);
    SoapySDRKwargs_clear(&args);
    if (!dev) {
        fprintf(stderr, "sdrplay_rx: cannot open %s: %s\n", argstr, SoapySDRDevice_lastError());
        return 1;
    }

    int rc = 0;
    if (antenna && SoapySDRDevice_setAntenna(dev, SOAPY_SDR_RX, 0, antenna) != 0)
        fprintf(stderr, "sdrplay_rx: antenna %s: %s\n", antenna, SoapySDRDevice_lastError());
    if (SoapySDRDevice_setSampleRate(dev, SOAPY_SDR_RX, 0, rate) != 0 ||
        SoapySDRDevice_setFrequency(dev, SOAPY_SDR_RX, 0, frequency, NULL) != 0) {
        fprintf(stderr, "sdrplay_rx: tuning failed: %s\n", SoapySDRDevice_lastError());
        SoapySDRDevice_unmake(dev);
        return 1;
    }
    for (int i = 0; i < n_settings; i++) {
        char key[64];
        const char *eq = strchr(settings[i], '=');
        if (!eq || (size_t)(eq - settings[i]) >= sizeof(key)) continue;
        memcpy(key, settings[i], (size_t)(eq - settings[i]));
        key[eq - settings[i]] = '\0';
        SoapySDRDevice_writeSetting(dev, key, eq + 1);
    }
    SoapySDRDevice_setGainMode(dev, SOAPY_SDR_RX, 0, agc);
    if (!agc && ifgr >= 0) SoapySDRDevice_setGainElement(dev, SOAPY_SDR_RX, 0, "IFGR", ifgr);
    if (lna >= 0) SoapySDRDevice_setGainElement(dev, SOAPY_SDR_RX, 0, "RFGR", lna);

    SoapySDRStream *stream = SoapySDRDevice_setupStream(dev, SOAPY_SDR_RX, SOAPY_SDR_CS16, NULL, 0, NULL);
    if (!stream || SoapySDRDevice_activateStream(dev, stream, 0, 0, 0) != 0) {
        fprintf(stderr, "sdrplay_rx: stream failed: %s\n", SoapySDRDevice_lastError());
        if (stream) SoapySDRDevice_closeStream(dev, stream);
        SoapySDRDevice_unmake(dev);
        return 1;
    }

    FILE *out = strcmp(output, "-") == 0 ? stdout : fopen(output, "wb");
    if (!out) {
        perror("sdrplay_rx: output");
        rc = 1;
    }
    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    signal(SIGPIPE, SIG_IGN); /* a closed pipe ends the loop through fwrite */

    size_t mtu = SoapySDRDevice_getStreamMTU(dev, stream);
    if (mtu == 0) mtu = 65536;
    int16_t *buffer = malloc(mtu * 2 * sizeof(int16_t));
    long long written = 0, overflows = 0;
    while (out && buffer && !stop_requested && (!max_samples || written < max_samples)) {
        void *buffs[] = {buffer};
        int flags = 0;
        long long time_ns = 0;
        int n = SoapySDRDevice_readStream(dev, stream, buffs, mtu, &flags, &time_ns, 1000000);
        if (n == SOAPY_SDR_TIMEOUT) continue;
        if (n == SOAPY_SDR_OVERFLOW) {
            overflows++;
            continue;
        }
        if (n < 0) {
            fprintf(stderr, "sdrplay_rx: read failed: %s\n", SoapySDR_errToStr(n));
            rc = 1;
            break;
        }
        long long count = n;
        if (max_samples && written + count > max_samples) count = max_samples - written;
        if (fwrite(buffer, 2 * sizeof(int16_t), (size_t)count, out) != (size_t)count) break;
        written += count;
    }
    if (out) fflush(out);
    if (overflows) fprintf(stderr, "sdrplay_rx: %lld overflows\n", overflows);

    free(buffer);
    if (out && out != stdout) fclose(out);
    SoapySDRDevice_deactivateStream(dev, stream, 0, 0);
    SoapySDRDevice_closeStream(dev, stream);
    SoapySDRDevice_unmake(dev);
    return rc;
}
