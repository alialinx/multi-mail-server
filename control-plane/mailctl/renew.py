from . import service


def main():
    service.renew_certs()
    print("certificates renewed")


if __name__ == "__main__":
    main()
