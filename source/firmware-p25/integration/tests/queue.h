/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "FreeRTOS.h"
QueueHandle_t xQueueCreate(unsigned,unsigned);
BaseType_t xQueueReceive(QueueHandle_t,void *,uint32_t);
BaseType_t xQueueSend(QueueHandle_t,const void *,uint32_t);
