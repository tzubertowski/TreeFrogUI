#include <stdio.h>
#include <stdlib.h>
#include "../ports/amprpc-mailbox-plan.h"

int main(int argc, char **argv)
{
    struct r36_amp_irq_plan plan;
    if (argc != 4)
        return 2;
    plan = r36_amp_plan_irq((unsigned int)strtoul(argv[1], NULL, 0),
                           (r36_amp_word)strtoul(argv[2], NULL, 0),
                           (r36_amp_word)strtoul(argv[3], NULL, 0));
    printf("%u %u %u %u %u\n", (unsigned int)plan.action,
           (unsigned int)plan.argument, (unsigned int)plan.acknowledge,
           (unsigned int)plan.clear_payload, (unsigned int)plan.release_receiver);
    return 0;
}
