/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "FreeRTOS.h"
BaseType_t xTaskCreate(void (*)(void *),const char *,unsigned,void *,unsigned,TaskHandle_t *);
