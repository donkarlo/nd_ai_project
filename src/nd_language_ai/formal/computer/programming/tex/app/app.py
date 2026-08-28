from application import LatexMergerApplication


def main() -> int:
    application = LatexMergerApplication()
    return application.run()


if __name__ == "__main__":
    raise SystemExit(main())
