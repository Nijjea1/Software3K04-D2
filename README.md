# ADC Part A, Deliverable 2

Python 3.9 or later. No third party packages.

## Run the system

    cd D2
    python3 -m adc.main

Then type `help`.

## Run the tests

    python3 -m unittest discover -s tests -t .

## Where the module boundaries are

    adc/hardware/   1.1  Hardware hiding    one file per device secret
    adc/behaviour/  1.2  Behaviour hiding   one file per behaviour secret
    adc/decisions/  1.3  Software decisions one file per representation secret
    adc/app.py      1    ADC Application    the only module that holds several references
    adc/main.py          demonstration front end, contains no behaviour

Every file opens with a docstring naming its Responsibility and its Secret.

## Demo scenarios

    login card-nurse / dispense MORPH-10MG 2 / confirm / take / close   normal path
    login card-nurse / replenish MORPH-10MG D1 5                        role refused
    login card-nurse / advance 121 / dispense MORPH-10MG 1              session timeout
    login card-old                                                      inactive account
    login card-nurse / dispense INSUL-100U 2 / confirm / close          UNCERTAIN, stock does not move
    dispense / confirm / openfault / status                             drawer fault, one drawer contained
    lockfault D2 / status                                               critical fault, enters FAULT
    login card-tech / clearfault / status                               fault recovery
    linkdown / dispense / confirm / take / close / queue / linkup        offline then ordered replay
    badmsg                                                              malformed inbound rejected

Credentials: card-nurse, card-pharm, card-tech, card-rev, card-old (inactive).
