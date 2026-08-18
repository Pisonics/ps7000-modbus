// Minimal PS7000 reader for .NET. Uses NModbus.
//
//   dotnet add package NModbus
//   dotnet add package System.IO.Ports
//   dotnet run -- COM3 1
//
// Pisonics -- https://www.pisonics.com

using System;
using System.IO.Ports;
using NModbus;
using NModbus.Serial;

namespace Pisonics
{
    /// <summary>Decoder for the PS7000 measurement block. No I/O.</summary>
    public static class Ps7000
    {
        public const ushort MeasureBlockStart = 1000;
        public const ushort MeasureBlockLenBase = 87;   // 1000-1086, all firmware
        public const ushort MeasureBlockLenExt  = 114;  // 1000-1113, SW 4.x, adds gas index

        // Registers are 1-based in the documentation; the frame carries one less.
        public static ushort FrameAddress(ushort registerNumber) => (ushort)(registerNumber - 1);

        private static int Index(ushort registerNumber) => registerNumber - MeasureBlockStart;

        public static ushort U16(ushort[] r, ushort reg) => r[Index(reg)];

        public static short I16(ushort[] r, ushort reg) => unchecked((short)r[Index(reg)]);

        /// <summary>CDAB: low word first. Getting this backwards is the
        /// number one cause of nonsense process values.</summary>
        public static uint U32(ushort[] r, ushort reg)
        {
            int i = Index(reg);
            return (uint)(r[i] | (r[i + 1] << 16));
        }

        public static float F32(ushort[] r, ushort reg) =>
            BitConverter.Int32BitsToSingle(unchecked((int)U32(r, reg)));

        // --- the fields most integrations actually need ---
        public static float MainValue(ushort[] r)      => F32(r, 1026);
        public static ushort MainValueUnit(ushort[] r) => U16(r, 1028);
        public static float ProbeTemperature(ushort[] r)  => F32(r, 1068);
        public static bool ProbeTemperatureValid(ushort[] r) => U16(r, 1067) != 0;
        public static float SignalQuality(ushort[] r)  => F32(r, 1007);
        public static float Loop1Current(ushort[] r)   => F32(r, 1045);
        public static uint  UpTimeSeconds(ushort[] r)  => U32(r, 1074);
        public static ushort MeasureErrorCode(ushort[] r) => U16(r, 1004);
        public static ushort GasIndexEma(ushort[] r)   => U16(r, 1113);

        private static readonly int[] StaleBits = { 0, 1, 3, 4, 6 };

        /// <summary>True when the instrument did not produce a new value this
        /// cycle. Do NOT use the `ok` field for this -- see docs/error-codes.md.</summary>
        public static bool ValueIsStale(ushort measureErrorCode)
        {
            foreach (int b in StaleBits)
                if ((measureErrorCode & (1 << b)) != 0) return true;
            return false;
        }

        public static string UnitName(ushort code) => code switch
        {
            0 => "g/cm3",
            1 => "% (volume)",
            2 => "% (mass)",
            3 => "degBe",
            4 => "g/L",
            5 => "kg/m3",
            _ => "?"
        };
    }

    public static class Program
    {
        public static void Main(string[] args)
        {
            string portName = args.Length > 0 ? args[0] : "COM3";
            byte slave = args.Length > 1 ? byte.Parse(args[1]) : (byte)1;

            using var port = new SerialPort(portName, 9600, Parity.None, 8, StopBits.One)
            {
                ReadTimeout = 1000,
                WriteTimeout = 1000
            };
            port.Open();

            var master = new ModbusFactory().CreateRtuMaster(port);

            ushort count = Ps7000.MeasureBlockLenExt;
            ushort[] regs;
            try
            {
                regs = master.ReadInputRegisters(
                    slave, Ps7000.FrameAddress(Ps7000.MeasureBlockStart), count);
            }
            catch (SlaveException)
            {
                // Older firmware has no gas-index registers and refuses the
                // longer read. Fall back rather than reporting a fault.
                count = Ps7000.MeasureBlockLenBase;
                regs = master.ReadInputRegisters(
                    slave, Ps7000.FrameAddress(Ps7000.MeasureBlockStart), count);
            }

            ushort err = Ps7000.MeasureErrorCode(regs);

            Console.WriteLine($"     main value : {Ps7000.MainValue(regs):F4} " +
                              Ps7000.UnitName(Ps7000.MainValueUnit(regs)));
            Console.WriteLine($"    probe temp. : {Ps7000.ProbeTemperature(regs):F2} degC" +
                              (Ps7000.ProbeTemperatureValid(regs) ? "" : "   (INVALID)"));
            Console.WriteLine($" signal quality : {Ps7000.SignalQuality(regs):F3}");
            Console.WriteLine($"         loop 1 : {Ps7000.Loop1Current(regs):F3} mA");
            Console.WriteLine($"        up time : {Ps7000.UpTimeSeconds(regs)} s");
            if (count == Ps7000.MeasureBlockLenExt)
                Console.WriteLine($"  entrained gas : {Ps7000.GasIndexEma(regs)} / 100");
            if (Ps7000.ValueIsStale(err))
                Console.WriteLine($"             !! : value is STALE (measureErrorCode 0x{err:X4})");
        }
    }
}
