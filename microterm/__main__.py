from microterm import Microterm

if __name__ == '__main__':
    try:
        Microterm().cmdloop()
    except KeyboardInterrupt:
        print('')