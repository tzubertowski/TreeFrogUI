obj-m := r36k.o
KDIR := /root/linux-4.4.186

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=mips CROSS_COMPILE=mipsel-linux-gnu- modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean
